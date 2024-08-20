import asyncio
import logging

from agnext.application import SingleThreadedAgentRuntime
from agnext.application.logging import EVENT_LOGGER_NAME
from agnext.core import AgentId, AgentProxy
from team_one.agents.file_surfer import FileSurfer
from team_one.agents.orchestrator import RoundRobinOrchestrator
from team_one.agents.user_proxy import UserProxy
from team_one.messages import RequestReplyMessage
from team_one.utils import LogHandler, create_completion_client_from_env


async def main() -> None:
    # Create the runtime.
    runtime = SingleThreadedAgentRuntime()

    # Get an appropriate client
    client = create_completion_client_from_env()

    # Register agents.
    await runtime.register(
        "file_surfer",
        lambda: FileSurfer(model_client=client),
    )
    file_surfer = AgentProxy(AgentId("file_surfer", "default"), runtime)

    await runtime.register(
        "UserProxy",
        lambda: UserProxy(),
    )
    user_proxy = AgentProxy(AgentId("UserProxy", "default"), runtime)

    await runtime.register("orchestrator", lambda: RoundRobinOrchestrator([file_surfer, user_proxy]))

    run_context = runtime.start()
    await runtime.send_message(RequestReplyMessage(), user_proxy.id)
    await run_context.stop_when_idle()


if __name__ == "__main__":
    logger = logging.getLogger(EVENT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    log_handler = LogHandler()
    logger.handlers = [log_handler]
    asyncio.run(main())
