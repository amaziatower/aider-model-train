import pytest
from agnext.application import SingleThreadedAgentRuntime
from agnext.core import AgentId
from agnext.core.exceptions import MessageDroppedException
from agnext.core.intervention import DefaultInterventionHandler, DropMessage
from test_utils import LoopbackAgent, MessageType


@pytest.mark.asyncio
async def test_intervention_count_messages() -> None:

    class DebugInterventionHandler(DefaultInterventionHandler):
        def __init__(self) -> None:
            self.num_messages = 0

        async def on_send(self, message: MessageType, *, sender: AgentId | None, recipient: AgentId) -> MessageType:
            self.num_messages += 1
            return message

    handler = DebugInterventionHandler()
    runtime = SingleThreadedAgentRuntime(intervention_handler=handler)
    loopback = runtime.register_and_get("name", LoopbackAgent)
    run_context = runtime.start()

    _response = await runtime.send_message(MessageType(), recipient=loopback)

    await run_context.stop()

    assert handler.num_messages == 1
    loopback_agent: LoopbackAgent = runtime._get_agent(loopback) # type: ignore
    assert loopback_agent.num_calls == 1

@pytest.mark.asyncio
async def test_intervention_drop_send() -> None:

    class DropSendInterventionHandler(DefaultInterventionHandler):
        async def on_send(self, message: MessageType, *, sender: AgentId | None, recipient: AgentId) -> MessageType | type[DropMessage]:
            return DropMessage

    handler = DropSendInterventionHandler()
    runtime = SingleThreadedAgentRuntime(intervention_handler=handler)

    loopback = runtime.register_and_get("name", LoopbackAgent)
    run_context = runtime.start()

    with pytest.raises(MessageDroppedException):
        _response = await runtime.send_message(MessageType(), recipient=loopback)

    await run_context.stop()

    loopback_agent: LoopbackAgent = runtime._get_agent(loopback) # type: ignore
    assert loopback_agent.num_calls == 0


@pytest.mark.asyncio
async def test_intervention_drop_response() -> None:

    class DropResponseInterventionHandler(DefaultInterventionHandler):
        async def on_response(self, message: MessageType, *, sender: AgentId, recipient: AgentId | None) -> MessageType | type[DropMessage]:
            return DropMessage

    handler = DropResponseInterventionHandler()
    runtime = SingleThreadedAgentRuntime(intervention_handler=handler)

    loopback = runtime.register_and_get("name", LoopbackAgent)
    run_context = runtime.start()

    with pytest.raises(MessageDroppedException):
        _response = await runtime.send_message(MessageType(), recipient=loopback)

    await run_context.stop()


@pytest.mark.asyncio
async def test_intervention_raise_exception_on_send() -> None:

    class InterventionException(Exception):
        pass

    class ExceptionInterventionHandler(DefaultInterventionHandler): # type: ignore
        async def on_send(self, message: MessageType, *, sender: AgentId | None, recipient: AgentId) -> MessageType | type[DropMessage]: # type: ignore
            raise InterventionException

    handler = ExceptionInterventionHandler()
    runtime = SingleThreadedAgentRuntime(intervention_handler=handler)

    long_running = runtime.register_and_get("name", LoopbackAgent)
    run_context = runtime.start()

    with pytest.raises(InterventionException):
        _response = await runtime.send_message(MessageType(), recipient=long_running)

    await run_context.stop()

    long_running_agent: LoopbackAgent = runtime._get_agent(long_running) # type: ignore
    assert long_running_agent.num_calls == 0

@pytest.mark.asyncio
async def test_intervention_raise_exception_on_respond() -> None:

    class InterventionException(Exception):
        pass

    class ExceptionInterventionHandler(DefaultInterventionHandler): # type: ignore
        async def on_response(self, message: MessageType, *, sender: AgentId, recipient: AgentId | None) -> MessageType | type[DropMessage]: # type: ignore
            raise InterventionException

    handler = ExceptionInterventionHandler()
    runtime = SingleThreadedAgentRuntime(intervention_handler=handler)

    long_running = runtime.register_and_get("name", LoopbackAgent)
    run_context = runtime.start()
    with pytest.raises(InterventionException):
        _response = await runtime.send_message(MessageType(), recipient=long_running)

    await run_context.stop()

    long_running_agent: LoopbackAgent = runtime._get_agent(long_running) # type: ignore
    assert long_running_agent.num_calls == 1
