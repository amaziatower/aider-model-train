import asyncio
import logging

from agnext.application import SingleThreadedAgentRuntime
from agnext.application.logging import EVENT_LOGGER_NAME
from agnext.components import DefaultSubscription
from agnext.core import AgentId, AgentProxy
from team_one.agents.coder import Coder, Executor
from team_one.agents.orchestrator import RoundRobinOrchestrator
from team_one.agents.user_proxy import UserProxy
from team_one.messages import RequestReplyMessage
from team_one.utils import LogHandler, create_completion_client_from_env


async def main() -> None:
    # Create the runtime.
    runtime = SingleThreadedAgentRuntime()

    # Register agents.
    await runtime.register(
        "Coder", lambda: Coder(model_client=create_completion_client_from_env()), lambda: [DefaultSubscription()]
    )
    coder = AgentProxy(AgentId("Coder", "default"), runtime)

    await runtime.register("Executor", lambda: Executor("A agent for executing code"), lambda: [DefaultSubscription()])
    executor = AgentProxy(AgentId("Executor", "default"), runtime)

    await runtime.register(
        "UserProxy",
        lambda: UserProxy(description="The current user interacting with you."),
        lambda: [DefaultSubscription()],
    )
    user_proxy = AgentProxy(AgentId("UserProxy", "default"), runtime)

    await runtime.register(
        "orchestrator", lambda: RoundRobinOrchestrator([coder, executor, user_proxy]), lambda: [DefaultSubscription()]
    )

    runtime.start()
    await runtime.send_message(RequestReplyMessage(), user_proxy.id)
    await runtime.stop_when_idle()


if __name__ == "__main__":
    logger = logging.getLogger(EVENT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    log_handler = LogHandler()
    logger.handlers = [log_handler]
    asyncio.run(main())
