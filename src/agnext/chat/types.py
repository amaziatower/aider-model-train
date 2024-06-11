from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Union

from ..components import FunctionCall, Image
from ..components.models import FunctionExecutionResultMessage


@dataclass(kw_only=True)
class BaseMessage:
    # Name of the agent that sent this message
    source: str


@dataclass
class TextMessage(BaseMessage):
    content: str


@dataclass
class MultiModalMessage(BaseMessage):
    content: List[Union[str, Image]]


@dataclass
class FunctionCallMessage(BaseMessage):
    content: List[FunctionCall]


Message = Union[TextMessage, MultiModalMessage, FunctionCallMessage, FunctionExecutionResultMessage]


class ResponseFormat(Enum):
    text = "text"
    json_object = "json_object"


@dataclass
class RespondNow:
    """A message to request a response from the addressed agent. The sender
    expects a response upon sening and waits for it synchronously."""

    response_format: ResponseFormat = field(default=ResponseFormat.text)


@dataclass
class PublishNow:
    """A message to request an event to be published to the addressed agent.
    Unlike RespondNow, the sender does not expect a response upon sending."""

    response_format: ResponseFormat = field(default=ResponseFormat.text)


class Reset: ...
