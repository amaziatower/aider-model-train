import inspect
import warnings
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionAssistantMessageParam,
    ChatCompletionContentPartParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionRole,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
    ChatCompletionUserMessageParam,
    completion_create_params,
)
from typing_extensions import Required, TypedDict, Unpack

from ..._pydantic import type2schema
from ...cache import AbstractCache
from ...oai.openai_utils import OAI_PRICE1K, get_key  # type: ignore
from ..image import Image
from ..model_client import ModelCapabilities, ModelClient
from ..types import (
    AssistantMessage,
    CreateResult,
    FunctionCall,
    FunctionCallMessage,
    FunctionDefinition,
    Message,
    RequestUsage,
    SystemMessage,
    UserMessage,
)
from . import model_info

openai_init_kwargs = set(inspect.getfullargspec(AsyncOpenAI.__init__).kwonlyargs)
aopenai_init_kwargs = set(inspect.getfullargspec(AsyncAzureOpenAI.__init__).kwonlyargs)

create_kwargs = set(completion_create_params.CompletionCreateParamsBase.__annotations__.keys()) | set(
    ("timeout", "stream")
)
# Only single choice allowed
disallowed_create_args = set(["stream", "messages", "function_call", "functions", "n"])
required_create_args = set(["model"])


def _openai_client_from_config(config: Mapping[str, Any]) -> Union[AsyncOpenAI, AsyncAzureOpenAI]:
    if config.get("api_type", None) is not None and config["api_type"].startswith("azure"):
        # Take a copy
        copied_config = dict(config).copy()

        # Do some fixups
        copied_config["azure_deployment"] = copied_config.get("azure_deployment", config.get("model"))
        if copied_config["azure_deployment"] is not None:
            copied_config["azure_deployment"] = copied_config["azure_deployment"].replace(".", "")
        copied_config["azure_endpoint"] = copied_config.get("azure_endpoint", copied_config.pop("base_url", None))

        # Shave down the config to just the AzureOpenAI kwargs
        azure_config = {k: v for k, v in copied_config.items() if k in aopenai_init_kwargs}
        return AsyncAzureOpenAI(**azure_config)
    else:
        # Shave down the config to just the OpenAI kwargs
        openai_config = {k: v for k, v in config.items() if k in openai_init_kwargs}
        return AsyncOpenAI(**openai_config)


def _create_args_from_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    create_args = {k: v for k, v in config.items() if k in create_kwargs}
    create_args_keys = set(create_args.keys())
    if not required_create_args.issubset(create_args_keys):
        raise ValueError(f"Required create args are missing: {required_create_args - create_args_keys}")
    if disallowed_create_args.intersection(create_args_keys):
        raise ValueError(f"Disallowed create args are present: {disallowed_create_args.intersection(create_args_keys)}")
    return create_args


oai_system_message_schema = type2schema(ChatCompletionSystemMessageParam)
oai_user_message_schema = type2schema(ChatCompletionUserMessageParam)
oai_assistant_message_schema = type2schema(ChatCompletionAssistantMessageParam)
oai_tool_message_schema = type2schema(ChatCompletionToolMessageParam)


def type_to_role(message: Message) -> ChatCompletionRole:
    if isinstance(message, SystemMessage):
        return "system"
    elif isinstance(message, UserMessage):
        return "user"
    elif isinstance(message, AssistantMessage):
        return "assistant"
    else:
        return "tool"


def user_message_to_oai(message: UserMessage) -> ChatCompletionUserMessageParam:
    if isinstance(message.content, str):
        return ChatCompletionUserMessageParam(
            content=message.content,
            role="user",
        )
    else:
        parts: List[ChatCompletionContentPartParam] = []
        for part in message.content:
            if isinstance(part, str):
                oai_part = ChatCompletionContentPartTextParam(
                    text=part,
                    type="text",
                )
                parts.append(oai_part)
            elif isinstance(part, Image):
                # TODO: support url based images
                # TODO: support specifying details
                parts.append(part.to_openai_format())
            else:
                raise ValueError(f"Unknown content type: {part}")
        return ChatCompletionUserMessageParam(
            content=parts,
            role="user",
        )


def system_message_to_oai(message: SystemMessage) -> ChatCompletionSystemMessageParam:
    return ChatCompletionSystemMessageParam(
        content=message.content,
        role="system",
    )


def func_call_to_oai(message: FunctionCall) -> ChatCompletionMessageToolCallParam:
    return ChatCompletionMessageToolCallParam(
        id=message.id,
        function={
            "arguments": message.arguments,
            "name": message.name,
        },
        type="function",
    )


def tool_message_to_oai(message: FunctionCallMessage) -> Sequence[ChatCompletionToolMessageParam]:
    return [
        ChatCompletionToolMessageParam(content=x.content, role="tool", tool_call_id=x.call_id)
        for x in message.call_results
    ]


def assistant_message_to_oai(message: AssistantMessage) -> ChatCompletionAssistantMessageParam:
    msg = ChatCompletionAssistantMessageParam(
        content=message.content,
        role="assistant",
    )
    if message.function_calls is not None:
        msg["tool_calls"] = [func_call_to_oai(x) for x in message.function_calls]

    return msg


def to_oai_type(message: Message) -> Sequence[ChatCompletionMessageParam]:
    if isinstance(message, SystemMessage):
        return [system_message_to_oai(message)]
    elif isinstance(message, UserMessage):
        return [user_message_to_oai(message)]
    elif isinstance(message, AssistantMessage):
        return [assistant_message_to_oai(message)]
    else:
        return tool_message_to_oai(message)


def _add_usage(usage1: RequestUsage, usage2: RequestUsage) -> RequestUsage:
    if usage1.cost is not None or usage2.cost is not None:
        cost = 0.0
        if usage1.cost is not None:
            cost += usage1.cost

        if usage2.cost is not None:
            cost += usage2.cost
    else:
        cost = None

    return RequestUsage(
        prompt_tokens=usage1.prompt_tokens + usage2.prompt_tokens,
        completion_tokens=usage1.completion_tokens + usage2.completion_tokens,
        cost=cost,
    )


def _cost(response: Union[ChatCompletion, Tuple[str, int, int]]) -> float:
    if isinstance(response, ChatCompletion):
        return _cost(
            (
                response.model,
                response.usage.prompt_tokens if response.usage is not None else 0,
                response.usage.completion_tokens if response.usage is not None else 0,
            )
        )

    """Calculate the cost of the response."""
    model, n_input_tokens, n_output_tokens = response

    if model not in OAI_PRICE1K:
        # TODO: add logging to warn that the model is not found
        # logger.debug(f"Model {model} is not found. The cost will be 0.", exc_info=True)
        return 0

    tmp_price1K = OAI_PRICE1K[model]
    # First value is input token rate, second value is output token rate
    if isinstance(tmp_price1K, tuple):
        return (tmp_price1K[0] * n_input_tokens + tmp_price1K[1] * n_output_tokens) / 1000  # type: ignore
    return tmp_price1K * (n_input_tokens + n_output_tokens) / 1000  # type: ignore


class ResponseFormat(TypedDict):
    type: Literal["text", "json_object"]


class CreateArguments(TypedDict, total=False):
    frequency_penalty: Optional[float]
    logit_bias: Optional[Dict[str, int]]
    max_tokens: Optional[int]
    n: Optional[int]
    presence_penalty: Optional[float]
    response_format: ResponseFormat
    seed: Optional[int]
    stop: Union[Optional[str], List[str]]
    temperature: Optional[float]
    top_p: Optional[float]
    user: str


AsyncAzureADTokenProvider = Callable[[], Union[str, Awaitable[str]]]


class BaseOpenAIClientConfiguration(CreateArguments, total=False):
    model: str
    api_key: str
    timeout: Union[float, None]
    max_retries: int


# See OpenAI docs for explanation of these parameters
class OpenAIClientConfiguration(BaseOpenAIClientConfiguration, total=False):
    organization: str
    base_url: str


class AzureOpenAIClientConfiguration(BaseOpenAIClientConfiguration, total=False):
    # Azure specific
    azure_endpoint: Required[str]
    azure_deployment: str
    api_version: str
    azure_ad_token: str
    azure_ad_token_provider: AsyncAzureADTokenProvider
    model_capabilities: Required[ModelCapabilities]


def convert_functions(functions: List[FunctionDefinition]) -> List[ChatCompletionToolParam]:
    result: List[ChatCompletionToolParam] = []
    for func in functions:
        result.append(
            {
                "type": "function",
                "function": {
                    "name": func.name,
                    "parameters": func.parameters,
                    "description": func.description,
                },
            }
        )
    return result


class BaseOpenAI(ModelClient):
    def __init__(
        self,
        client: Union[AsyncOpenAI, AsyncAzureOpenAI],
        create_args: Dict[str, Any],
        model_capabilities: Optional[ModelCapabilities] = None,
    ):
        self._client = client
        if model_capabilities is None and isinstance(client, AsyncAzureOpenAI):
            raise ValueError("AzureOpenAI requires explicit model capabilities")
        elif model_capabilities is None:
            self._model_capabilities = model_info.get_capabilties(create_args["model"])
        else:
            self._model_capabilities = model_capabilities

        self._resolved_model: Optional[str] = None
        if "model" in create_args:
            self._resolved_model = model_info.resolve_model(create_args["model"])

        if (
            "response_format" in create_args
            and create_args["response_format"]["type"] == "json_object"
            and not self._model_capabilities["json_output"]
        ):
            raise ValueError("Model does not support JSON output")

        self._create_args = create_args
        self._total_usage = RequestUsage(prompt_tokens=0, completion_tokens=0, cost=0.0)
        self._actual_usage = RequestUsage(prompt_tokens=0, completion_tokens=0, cost=0.0)

    @classmethod
    def create_from_config(cls, config: Dict[str, Any]) -> ModelClient:
        return OpenAI(**config)

    async def create(
        self,
        messages: List[Message],
        cache: Optional[AbstractCache] = None,
        functions: List[FunctionDefinition] = [],
        json_output: Optional[bool] = None,
        extra_create_args: Dict[str, Any] = {},
    ) -> CreateResult:
        # Make sure all extra_create_args are valid
        extra_create_args_keys = set(extra_create_args.keys())
        if not create_kwargs.issuperset(extra_create_args_keys):
            raise ValueError(f"Extra create args are invalid: {extra_create_args_keys - create_kwargs}")

        # Copy the create args and overwrite anything in extra_create_args
        create_args = self._create_args.copy()
        create_args.update(extra_create_args)

        # TODO: allow custom handling.
        # For now we raise an error if images are present and vision is not supported
        if self.capabilities["vision"] is False:
            for message in messages:
                if isinstance(message, UserMessage):
                    if isinstance(message.content, list) and any(isinstance(x, Image) for x in message.content):
                        raise ValueError("Model does not support vision and image was provided")

        if json_output is not None:
            if self.capabilities["json_output"] is False and json_output is True:
                raise ValueError("Model does not support JSON output")

            if json_output is True:
                create_args["response_format"] = {"type": "json_object"}
            else:
                create_args["response_format"] = {"type": "text"}

        if self.capabilities["json_output"] is False and json_output is True:
            raise ValueError("Model does not support JSON output")

        oai_messages_nested = [to_oai_type(m) for m in messages]
        oai_messages = [item for sublist in oai_messages_nested for item in sublist]

        cache_key = None
        if cache is not None:
            cache_key = get_key({**create_args, "messages": oai_messages})
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                response = cast(CreateResult, cached_value)
                response.cached = True
                _add_usage(self._total_usage, response.usage)
                return response

        if self.capabilities["function_calling"] is False and len(functions) > 0:
            raise ValueError("Model does not support function calling")

        if len(functions) > 0:
            tools = convert_functions(functions)
            result = await self._client.chat.completions.create(
                messages=oai_messages, stream=False, tools=tools, **create_args
            )
        else:
            result = await self._client.chat.completions.create(messages=oai_messages, stream=False, **create_args)

        usage = RequestUsage(
            # TODO backup token counting
            prompt_tokens=result.usage.prompt_tokens if result.usage is not None else 0,
            completion_tokens=result.usage.completion_tokens if result.usage is not None else 0,
            cost=_cost(result),
        )

        if self._resolved_model is not None:
            if self._resolved_model != result.model:
                warnings.warn(
                    f"Resolved model mismatch: {self._resolved_model} != {result.model}. AutoGen model mapping may be incorrect."
                )

        # Limited to a single choice currently.
        choice = result.choices[0]
        if choice.finish_reason == "function_call":
            raise ValueError("Function calls are not supported in this context")

        content: Union[str, List[FunctionCall]]
        if choice.finish_reason == "tool_calls":
            assert choice.message.tool_calls is not None
            assert choice.message.function_call is None

            # NOTE: If OAI response type changes, this will need to be updated
            content = [
                FunctionCall(id=x.id, arguments=x.function.arguments, name=x.function.name)
                for x in choice.message.tool_calls
            ]
            finish_reason = "function_calls"
        else:
            finish_reason = choice.finish_reason
            content = choice.message.content or ""

        response = CreateResult(finish_reason=finish_reason, content=content, usage=usage, cached=False)  # type: ignore

        if cache is not None:
            assert cache_key is not None
            cache.set(cache_key, result)

        _add_usage(self._actual_usage, usage)
        _add_usage(self._total_usage, usage)

        # TODO - why is this cast needed?
        return response

    async def create_stream(
        self,
        messages: List[Message],
        cache: Optional[AbstractCache] = None,
        functions: List[FunctionDefinition] = [],
        json_output: Optional[bool] = None,
        extra_create_args: Dict[str, Any] = {},
    ) -> AsyncGenerator[Union[str, CreateResult], None]:
        # Make sure all extra_create_args are valid
        extra_create_args_keys = set(extra_create_args.keys())
        if not create_kwargs.issuperset(extra_create_args_keys):
            raise ValueError(f"Extra create args are invalid: {extra_create_args_keys - create_kwargs}")

        # Copy the create args and overwrite anything in extra_create_args
        create_args = self._create_args.copy()
        create_args.update(extra_create_args)

        cache_key = None
        if cache is not None:
            cache_key = get_key({**create_args, "messages": messages})
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                response = cast(CreateResult, cached_value)
                response.cached = True
                _add_usage(self._total_usage, response.usage)
                yield response

        oai_messages_nested = [to_oai_type(m) for m in messages]
        oai_messages = [item for sublist in oai_messages_nested for item in sublist]

        # TODO: allow custom handling.
        # For now we raise an error if images are present and vision is not supported
        if self.capabilities["vision"] is False:
            for message in messages:
                if isinstance(message, UserMessage):
                    if isinstance(message.content, list) and any(isinstance(x, Image) for x in message.content):
                        raise ValueError("Model does not support vision and image was provided")

        if json_output is not None:
            if self.capabilities["json_output"] is False and json_output is True:
                raise ValueError("Model does not support JSON output")

            if json_output is True:
                create_args["response_format"] = {"type": "json_object"}
            else:
                create_args["response_format"] = {"type": "text"}

        if len(functions) > 0:
            tools = convert_functions(functions)
            stream = await self._client.chat.completions.create(
                messages=oai_messages, stream=True, tools=tools, **create_args
            )
        else:
            stream = await self._client.chat.completions.create(messages=oai_messages, stream=True, **create_args)

        stop_reason = None
        maybe_model = None
        content_deltas: List[str] = []
        full_tool_calls: Dict[int, FunctionCall] = {}
        completion_tokens = 0

        async for chunk in stream:
            choice = chunk.choices[0]
            stop_reason = choice.finish_reason
            maybe_model = chunk.model

            # First try get content
            if choice.delta.content is not None:
                content_deltas.append(choice.delta.content)
                if len(choice.delta.content) > 0:
                    yield choice.delta.content
                continue

            # Otherwise, get tool calls
            if choice.delta.tool_calls is not None:
                for tool_call_chunk in choice.delta.tool_calls:
                    idx = tool_call_chunk.index
                    if idx not in full_tool_calls:
                        # We ignore the type hint here because we want to fill in type when the delta provides it
                        full_tool_calls[idx] = FunctionCall(id="", arguments="", name="")

                    if tool_call_chunk.id is not None:
                        full_tool_calls[idx].id += tool_call_chunk.id

                    if tool_call_chunk.function is not None:
                        if tool_call_chunk.function.name is not None:
                            full_tool_calls[idx].name += tool_call_chunk.function.name
                        if tool_call_chunk.function.arguments is not None:
                            full_tool_calls[idx].arguments += tool_call_chunk.function.arguments

        model = maybe_model or create_args["model"]
        model = model.replace("gpt-35", "gpt-3.5")  # hack for Azure API

        # TODO fix count token
        prompt_tokens = 0
        # prompt_tokens = count_token(messages, model=model)
        if stop_reason is None:
            raise ValueError("No stop reason found")

        content: Union[str, List[FunctionCall]]
        if len(content_deltas) > 1:
            content = "".join(content_deltas)
            completion_tokens = 0
            # completion_tokens = count_token(content, model=model)
        else:
            completion_tokens = 0
            # TODO: fix assumption that dict values were added in order and actually order by int index
            # for tool_call in full_tool_calls.values():
            #     # value = json.dumps(tool_call)
            #     # completion_tokens += count_token(value, model=model)
            #     completion_tokens += 0
            content = list(full_tool_calls.values())

        usage = RequestUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=_cost((model, prompt_tokens, completion_tokens)),
        )
        if stop_reason == "function_call":
            raise ValueError("Function calls are not supported in this context")
        if stop_reason == "tool_calls":
            stop_reason = "function_calls"

        result = CreateResult(finish_reason=stop_reason, content=content, usage=usage, cached=False)

        if cache is not None:
            assert cache_key is not None
            cache.set(cache_key, result)

        _add_usage(self._actual_usage, usage)
        _add_usage(self._total_usage, usage)

        yield result

    def actual_usage(self) -> RequestUsage:
        return self._actual_usage

    def total_usage(self) -> RequestUsage:
        return self._total_usage

    @property
    def capabilities(self) -> ModelCapabilities:
        return self._model_capabilities


class OpenAI(BaseOpenAI):
    def __init__(self, **kwargs: Unpack[OpenAIClientConfiguration]):
        if "model" not in kwargs:
            raise ValueError("model is required for OpenAI")

        client = _openai_client_from_config(kwargs)
        create_args = _create_args_from_config(kwargs)
        super().__init__(client, create_args)


class AzureOpenAI(BaseOpenAI):
    def __init__(self, **kwargs: Unpack[AzureOpenAIClientConfiguration]):
        if "model" in kwargs and "azure_deployment" in kwargs:
            raise ValueError("Cannot specify both model and azure_deployment")

        if "model" in kwargs:
            kwargs["azure_deployment"] = kwargs["model"]
            del kwargs["model"]

        client = _openai_client_from_config(kwargs)
        create_args = _create_args_from_config(kwargs)
        super().__init__(client, create_args)
