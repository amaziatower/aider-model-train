import asyncio

from agnext.application import SingleThreadedAgentRuntime
from agnext.components.models import OpenAIChatCompletionClient, UserMessage
from team_one.agents.file_surfer import FileSurfer
from team_one.messages import BroadcastMessage, RequestReplyMessage


async def main() -> None:
    # Create the runtime.
    runtime = SingleThreadedAgentRuntime()

    # Register agents.
    file_surfer = runtime.register_and_get(
        "file_surfer",
        lambda: FileSurfer(model_client=OpenAIChatCompletionClient(model="gpt-4o")),
    )
    task = input(f"Enter a task for {file_surfer.name}: ")
    msg = BroadcastMessage(content=UserMessage(content=task, source="human"))

    # Send a task to the tool user.
    await runtime.publish_message(msg, namespace="default")
    await runtime.publish_message(RequestReplyMessage(), namespace="default")

    # Run the runtime until the task is completed.
    await runtime.process_until_idle()


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("agnext").setLevel(logging.DEBUG)
    asyncio.run(main())
