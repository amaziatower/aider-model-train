import asyncio
from typing import Any, AsyncGenerator, List

import pytest
from agnext.components import Image
from agnext.components.models import (
    AssistantMessage,
    AzureOpenAIChatCompletionClient,
    CreateResult,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    LLMMessage,
    OpenAIChatCompletionClient,
    SystemMessage,
    UserMessage,
)
from agnext.components.models._model_info import resolve_model
from agnext.components.tools import FunctionTool
from agnext.core import CancellationToken
from openai.resources.chat.completions import AsyncCompletions
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage


async def _mock_create_stream(*args: Any, **kwargs: Any) -> AsyncGenerator[ChatCompletionChunk, None]:
    model = resolve_model(kwargs.get("model", "gpt-4o"))
    chunks = ["Hello", " Another Hello", " Yet Another Hello"]
    for chunk in chunks:
        await asyncio.sleep(0.1)
        yield ChatCompletionChunk(
            id="id",
            choices=[
                ChunkChoice(
                    finish_reason="stop",
                    index=0,
                    delta=ChoiceDelta(
                        content=chunk,
                        role="assistant",
                    ),
                )
            ],
            created=0,
            model=model,
            object="chat.completion.chunk",
        )


async def _mock_create(
    *args: Any, **kwargs: Any
) -> ChatCompletion | AsyncGenerator[ChatCompletionChunk, None]:
    stream = kwargs.get("stream", False)
    model = resolve_model(kwargs.get("model", "gpt-4o"))
    if not stream:
        await asyncio.sleep(0.1)
        return ChatCompletion(
            id="id",
            choices=[
                Choice(finish_reason="stop", index=0, message=ChatCompletionMessage(content="Hello", role="assistant"))
            ],
            created=0,
            model=model,
            object="chat.completion",
            usage=CompletionUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )
    else:
        return _mock_create_stream(*args, **kwargs)

@pytest.mark.asyncio
async def test_openai_chat_completion_client() -> None:
    client = OpenAIChatCompletionClient(model="gpt-4o", api_key="api_key")
    assert client


@pytest.mark.asyncio
async def test_azure_openai_chat_completion_client() -> None:
    client = AzureOpenAIChatCompletionClient(
        model="gpt-4o",
        api_key="api_key",
        api_version="2020-08-04",
        azure_endpoint="https://dummy.com",
        model_capabilities={"vision": True, "function_calling": True, "json_output": True},
    )
    assert client


@pytest.mark.asyncio
async def test_openai_chat_completion_client_create(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AsyncCompletions, "create", _mock_create)
    client = OpenAIChatCompletionClient(model="gpt-4o", api_key="api_key")
    result = await client.create(messages=[UserMessage(content="Hello", source="user")])
    assert result.content == "Hello"


@pytest.mark.asyncio
async def test_openai_chat_completion_client_create_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AsyncCompletions, "create", _mock_create)
    client = OpenAIChatCompletionClient(model="gpt-4o", api_key="api_key")
    chunks: List[str | CreateResult] = []
    async for chunk in client.create_stream(messages=[UserMessage(content="Hello", source="user")]):
        chunks.append(chunk)
    assert chunks[0] == "Hello"
    assert chunks[1] == " Another Hello"
    assert chunks[2] == " Yet Another Hello"
    assert isinstance(chunks[-1], CreateResult)
    assert chunks[-1].content == "Hello Another Hello Yet Another Hello"


@pytest.mark.asyncio
async def test_openai_chat_completion_client_create_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AsyncCompletions, "create", _mock_create)
    client = OpenAIChatCompletionClient(model="gpt-4o", api_key="api_key")
    cancellation_token = CancellationToken()
    task = asyncio.create_task(
        client.create(messages=[UserMessage(content="Hello", source="user")], cancellation_token=cancellation_token)
    )
    cancellation_token.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_openai_chat_completion_client_create_stream_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AsyncCompletions, "create", _mock_create)
    client = OpenAIChatCompletionClient(model="gpt-4o", api_key="api_key")
    cancellation_token = CancellationToken()
    stream = client.create_stream(
        messages=[UserMessage(content="Hello", source="user")], cancellation_token=cancellation_token
    )
    assert await anext(stream)
    cancellation_token.cancel()
    with pytest.raises(asyncio.CancelledError):
        async for _ in stream:
            pass


@pytest.mark.asyncio
async def test_openai_chat_completion_client_count_tokens() -> None:
    client = OpenAIChatCompletionClient(model="gpt-4o", api_key="api_key")
    messages: List[LLMMessage] = [
        SystemMessage(content="Hello"),
        UserMessage(content="Hello", source="user"),
        AssistantMessage(content="Hello", source="assistant"),
        UserMessage(
            content=[
                "str1",
                Image.from_base64(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
                ),
            ],
            source="user",
        ),
        FunctionExecutionResultMessage(content=[FunctionExecutionResult(content="Hello", call_id="1")]),
    ]

    def tool1(test: str, test2: str) -> str:
        return test + test2

    def tool2(test1: int, test2: List[int]) -> str:
        return str(test1) + str(test2)

    tools = [FunctionTool(tool1, description="example tool 1"), FunctionTool(tool2, description="example tool 2")]
    num_tokens = client.count_tokens(messages, tools=tools)
    assert num_tokens

    remaining_tokens = client.remaining_tokens(messages, tools=tools)
    assert remaining_tokens
