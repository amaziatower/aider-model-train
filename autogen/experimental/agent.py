from typing import AsyncGenerator, List, Protocol, Tuple, Union, runtime_checkable

from .types import IntermediateResponse, Message, MessageAndSender, MessageContext

GenerateReplyResult = Union[Message, Tuple[Message, MessageContext]]


@runtime_checkable
class Agent(Protocol):
    """(In preview) A protocol for Agent.

    An agent can communicate with other agents and perform actions.
    Different agents can differ in what actions they perform in the `receive` method.
    """

    @property
    def name(self) -> str:
        """The name of the agent."""
        ...

    @property
    def description(self) -> str:
        """The description of the agent. Used for the agent's introduction in
        a group chat setting."""
        ...

    async def generate_reply(
        self,
        messages: List[MessageAndSender],
    ) -> GenerateReplyResult: ...


@runtime_checkable
class AgentStream(Agent, Protocol):
    def stream_generate_reply(
        self,
        messages: List[MessageAndSender],
    ) -> AsyncGenerator[Union[IntermediateResponse, GenerateReplyResult], None]: ...
