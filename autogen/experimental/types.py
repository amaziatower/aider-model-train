from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from typing_extensions import Literal

from autogen.experimental.termination import TerminationResult

if TYPE_CHECKING:
    from .chat_result import ChatResult

from .agent import Agent
from .image import Image


@dataclass
class FunctionCall:
    id: str
    # JSON args
    arguments: str
    # Function to call
    name: str


@dataclass
class FunctionDefinition:
    name: str
    parameters: Dict[str, Any]
    description: str


@dataclass
class RequestUsage:
    prompt_tokens: int
    completion_tokens: int
    cost: Optional[float]


@dataclass
class UserMessageContentPartText:
    text: str


@dataclass
class SystemMessage:
    content: str


@dataclass
class UserMessage:
    content: Union[str, List[Union[str, Image]]]
    is_termination: bool = False


@dataclass
class AssistantMessage:
    content: Optional[str] = None
    function_calls: Optional[List[FunctionCall]] = None


@dataclass
class FunctionCallResult:
    content: str
    call_id: str


@dataclass
class FunctionCallMessage:
    call_results: List[FunctionCallResult]


Message = Union[SystemMessage, UserMessage, AssistantMessage, FunctionCallMessage]


@dataclass
class MessageContext:
    # If this agent modified the input, this should be set
    input: Optional[List[Message]] = None

    # If this agent initiated a nested conversation, this should be set
    nested_chat_result: Optional[ChatResult] = None

    # Who sent this message?
    sender: Optional[Agent] = None

    # Why was this speaker chosen?
    speaker_selection_reason: Optional[str] = None

    termination_result: Optional[TerminationResult] = None


FinishReasons = Literal["stop", "length", "function_calls", "content_filter"]


@dataclass
class CreateResult:
    finish_reason: FinishReasons
    content: Union[str, List[FunctionCall]]
    usage: RequestUsage
    cached: bool


@dataclass
class PartialContent:
    content: str


@dataclass
class StatusUpdate:
    content: str


@dataclass
class IntermediateResponse:
    item: Union[PartialContent, StatusUpdate]


GenerateReplyResult = Union[Message, Tuple[Message, MessageContext]]
