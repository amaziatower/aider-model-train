from typing import List, Tuple

from agnext.components.models import (
    AssistantMessage,
    LLMMessage,
    UserMessage,
)
from agnext.core import CancellationToken

from team_one.messages import (
    BroadcastMessage,
    RequestReplyMessage,
    ResetMessage,
    UserContent,
)

from ..utils import message_content_to_str
from .base_agent import TeamOneBaseAgent


class BaseWorker(TeamOneBaseAgent):
    """Base agent that handles the TeamOne worker behavior protocol."""

    def __init__(
        self,
        description: str,
        handle_messages_concurrently: bool = False,
    ) -> None:
        super().__init__(description, handle_messages_concurrently=handle_messages_concurrently)
        self._chat_history: List[LLMMessage] = []

    async def _handle_broadcast(self, message: BroadcastMessage, cancellation_token: CancellationToken) -> None:
        assert isinstance(message.content, UserMessage)
        self._chat_history.append(message.content)

    async def _handle_reset(self, message: ResetMessage, cancellation_token: CancellationToken) -> None:
        """Handle a reset message."""
        await self._reset(cancellation_token)

    async def _handle_request_reply(self, message: RequestReplyMessage, cancellation_token: CancellationToken) -> None:
        """Respond to a reply request."""
        request_halt, response = await self._generate_reply(cancellation_token)

        assistant_message = AssistantMessage(content=message_content_to_str(response), source=self.metadata["type"])
        self._chat_history.append(assistant_message)

        user_message = UserMessage(content=response, source=self.metadata["type"])
        await self.publish_message(BroadcastMessage(content=user_message, request_halt=request_halt))

    async def _generate_reply(self, cancellation_token: CancellationToken) -> Tuple[bool, UserContent]:
        """Returns (request_halt, response_message)"""
        raise NotImplementedError()

    async def _reset(self, cancellation_token: CancellationToken) -> None:
        self._chat_history = []
