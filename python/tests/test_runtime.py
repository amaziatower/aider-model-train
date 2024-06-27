import pytest
from agnext.application import SingleThreadedAgentRuntime
from agnext.core import AgentId, AgentRuntime
from test_utils import CascadingAgent, CascadingMessageType, LoopbackAgent, MessageType, NoopAgent


@pytest.mark.asyncio
async def test_agent_names_must_be_unique() -> None:
    runtime = SingleThreadedAgentRuntime()

    def agent_factory(runtime: AgentRuntime, id: AgentId) -> NoopAgent:
        assert id == AgentId("name1", "default")
        agent = NoopAgent()
        assert agent.id == id
        return agent

    agent1 = runtime.register_and_get("name1", agent_factory)
    assert agent1 == AgentId("name1", "default")

    with pytest.raises(ValueError):
        _agent1 = runtime.register_and_get("name1", NoopAgent)

    _agent1 = runtime.register_and_get("name3", NoopAgent)


@pytest.mark.asyncio
async def test_register_receives_publish() -> None:
    runtime = SingleThreadedAgentRuntime()

    runtime.register("name", LoopbackAgent)
    await runtime.publish_message(MessageType(), namespace="default")

    await runtime.process_until_idle()

    # Agent in default namespace should have received the message
    long_running_agent: LoopbackAgent = runtime._get_agent(runtime.get("name")) # type: ignore
    assert long_running_agent.num_calls == 1

    # Agent in other namespace should not have received the message
    other_long_running_agent: LoopbackAgent = runtime._get_agent(runtime.get("name", namespace="other")) # type: ignore
    assert other_long_running_agent.num_calls == 0


@pytest.mark.asyncio
async def test_register_receives_publish_cascade() -> None:
    runtime = SingleThreadedAgentRuntime()
    num_agents = 5
    num_initial_messages = 5
    max_rounds = 5
    total_num_calls_expected = 0
    for i in range(0, max_rounds):
        total_num_calls_expected += num_initial_messages * ((num_agents - 1) ** i)

    # Register agents
    for i in range(num_agents):
        runtime.register(f"name{i}", lambda: CascadingAgent(max_rounds))
    
    # Publish messages
    for _ in range(num_initial_messages):
        await runtime.publish_message(CascadingMessageType(round=1), namespace="default")

    # Process until idle.
    await runtime.process_until_idle()

    # Check that each agent received the correct number of messages.
    for i in range(num_agents):
        agent: CascadingAgent = runtime._get_agent(runtime.get(f"name{i}")) # type: ignore
        assert agent.num_calls == total_num_calls_expected
