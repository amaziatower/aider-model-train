import asyncio
import os

from agnext.application import SingleThreadedAgentRuntime
from agnext.components import Image, TypeRoutedAgent, message_handler
from agnext.core import MessageContext, TopicId
from app import build_app
from dotenv import load_dotenv
from messages import ArticleCreated, AuditorAlert, AuditText, GraphicDesignCreated


class Printer(TypeRoutedAgent):
    def __init__(
        self,
    ) -> None:
        super().__init__("")

    @message_handler
    async def handle_graphic_design(self, message: GraphicDesignCreated, ctx: MessageContext) -> None:
        image = Image.from_uri(message.imageUri)
        # Save image to random name in current directory
        image.image.save(os.path.join(os.getcwd(), f"{message.UserId}.png"))
        print(f"Received GraphicDesignCreated: user {message.UserId}, saved to {message.UserId}.png")

    @message_handler
    async def handle_auditor_alert(self, message: AuditorAlert, ctx: MessageContext) -> None:
        print(f"Received AuditorAlert: {message.auditorAlertMessage} for user {message.UserId}")


async def main() -> None:
    runtime = SingleThreadedAgentRuntime()
    await build_app(runtime)
    await runtime.register("Printer", lambda: Printer())

    ctx = runtime.start()

    topic_id = TopicId("default", "default")

    await runtime.publish_message(
        AuditText(text="Buy my product for a MASSIVE 50% discount.", UserId="user-1"), topic_id=topic_id
    )

    await runtime.publish_message(
        ArticleCreated(article="The best article ever written about trees and rocks", UserId="user-2"),
        topic_id=topic_id,
    )

    await ctx.stop_when_idle()


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
