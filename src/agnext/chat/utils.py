from typing import List, Optional, Union

from typing_extensions import Literal

from agnext.chat.types import (
    FunctionCallMessage,
    FunctionExecutionResultMessage,
    Message,
    MultiModalMessage,
    TextMessage,
)
from agnext.components.types import (
    AssistantMessage,
    LLMMessage,
    UserMessage,
)
from agnext.components.types import (
    FunctionExecutionResult as FunctionExecutionResultType,
)
from agnext.components.types import (
    FunctionExecutionResultMessage as FunctionExecutionResultMessageType,
)


def convert_content_message_to_assistant_message(
    message: Union[TextMessage, MultiModalMessage, FunctionCallMessage],
    handle_unrepresentable: Literal["error", "ignore", "try_slice"] = "error",
) -> Optional[AssistantMessage]:
    match message:
        case TextMessage() | FunctionCallMessage():
            return AssistantMessage(content=message.content, source=message.source)
        case MultiModalMessage():
            if handle_unrepresentable == "error":
                raise ValueError("Cannot represent multimodal message as AssistantMessage")
            elif handle_unrepresentable == "ignore":
                return None
            elif handle_unrepresentable == "try_slice":
                return AssistantMessage(
                    content="".join([x for x in message.content if isinstance(x, str)]),
                    source=message.source,
                )


def convert_content_message_to_user_message(
    message: Union[TextMessage, MultiModalMessage, FunctionCallMessage],
    handle_unrepresentable: Literal["error", "ignore", "try_slice"] = "error",
) -> Optional[UserMessage]:
    match message:
        case TextMessage() | MultiModalMessage():
            return UserMessage(content=message.content, source=message.source)
        case FunctionCallMessage():
            if handle_unrepresentable == "error":
                raise ValueError("Cannot represent multimodal message as UserMessage")
            elif handle_unrepresentable == "ignore":
                return None
            elif handle_unrepresentable == "try_slice":
                # TODO: what is a sliced function call?
                raise NotImplementedError("Sliced function calls not yet implemented")


def convert_tool_call_response_message(
    message: FunctionExecutionResultMessage,
    handle_unrepresentable: Literal["error", "ignore", "try_slice"] = "error",
) -> Optional[FunctionExecutionResultMessageType]:
    match message:
        case FunctionExecutionResultMessage():
            return FunctionExecutionResultMessageType(
                content=[FunctionExecutionResultType(content=x.content, call_id=x.call_id) for x in message.content]
            )


def convert_messages_to_llm_messages(
    messages: List[Message],
    self_name: str,
    handle_unrepresentable: Literal["error", "ignore", "try_slice"] = "error",
) -> List[LLMMessage]:
    result: List[LLMMessage] = []
    for message in messages:
        match message:
            case (
                TextMessage(_, source=source)
                | MultiModalMessage(_, source=source)
                | FunctionCallMessage(_, source=source)
            ) if source == self_name:
                converted_message_1 = convert_content_message_to_assistant_message(message, handle_unrepresentable)
                if converted_message_1 is not None:
                    result.append(converted_message_1)
            case (
                TextMessage(_, source=source)
                | MultiModalMessage(_, source=source)
                | FunctionCallMessage(_, source=source)
            ) if source != self_name:
                converted_message_2 = convert_content_message_to_user_message(message, handle_unrepresentable)
                if converted_message_2 is not None:
                    result.append(converted_message_2)
            case FunctionExecutionResultMessage(_, source=source) if source == self_name:
                converted_message_3 = convert_tool_call_response_message(message, handle_unrepresentable)
                if converted_message_3 is not None:
                    result.append(converted_message_3)
            case _:
                raise AssertionError("unreachable")

    return result
