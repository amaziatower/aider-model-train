from agnext.components import RoutedAgent, message_handler
from agnext.components.models import UserMessage
from agnext.core import MessageContext, TopicId

from ..messages import BroadcastMessage, RequestReplyMessage


class ReflexAgent(RoutedAgent):
    def __init__(self, description: str) -> None:
        super().__init__(description)

    @message_handler
    async def handle_incoming_message(self, message: BroadcastMessage, ctx: MessageContext) -> None:
        """Handle an incoming message."""
        pass

    @message_handler
    async def handle_request_reply_message(self, message: RequestReplyMessage, ctx: MessageContext) -> None:
        name = self.metadata["type"]

        response_message = UserMessage(
            content=f"Hello, world from {name}!",
            source=name,
        )
        topic_id = TopicId("default", self.id.key)

        await self.publish_message(BroadcastMessage(response_message), topic_id=topic_id)
