from autogen_core.application import SingleThreadedAgentRuntime
from autogen_core.components import TypeSubscription
from autogen_core.base import TopicId, AgentId
import pytest
from autogen_core.application import SingleThreadedAgentRuntime
from autogen_core.components import TypeSubscription, DefaultTopicId
from autogen_core.base import AgentId
from autogen_core.base import TopicId
from test_utils import LoopbackAgent, MessageType

import pytest

from autogen_core.base.exceptions import CantHandleException

def test_type_subscription_match() -> None:
    sub = TypeSubscription(topic_type="t1", agent_type="a1")

    assert sub.is_match(TopicId(type="t0", source="s1")) == False
    assert sub.is_match(TopicId(type="t1", source="s1")) == True
    assert sub.is_match(TopicId(type="t1", source="s2")) == True


def test_type_subscription_map() -> None:
    sub = TypeSubscription(topic_type="t1", agent_type="a1")

    assert sub.map_to_agent(TopicId(type="t1", source="s1")) == AgentId(type="a1", key="s1")

    with pytest.raises(CantHandleException):
        _agent_id = sub.map_to_agent(TopicId(type="t0", source="s1"))


@pytest.mark.asyncio
async def test_non_default_default_subscription() -> None:
    runtime = SingleThreadedAgentRuntime()

    await runtime.register("MyAgent", LoopbackAgent)
    runtime.start()
    await runtime.publish_message(MessageType(), topic_id=DefaultTopicId())
    await runtime.stop_when_idle()

    # Not subscribed
    agent_instance = await runtime.try_get_underlying_agent_instance(AgentId("MyAgent", key="default"), type=LoopbackAgent)
    assert agent_instance.num_calls == 0

    # Subscribed
    default_subscription = TypeSubscription("default", "MyAgent")
    await runtime.add_subscription(default_subscription)

    runtime.start()
    await runtime.publish_message(MessageType(), topic_id=DefaultTopicId())
    await runtime.stop_when_idle()

    assert agent_instance.num_calls == 1

    # Publish to a different unsubscribed topic
    runtime.start()
    await runtime.publish_message(MessageType(), topic_id=DefaultTopicId(type="other"))
    await runtime.stop_when_idle()

    assert agent_instance.num_calls == 1

    # Add a subscription to the other topic
    await runtime.add_subscription(TypeSubscription("other", "MyAgent"))

    runtime.start()
    await runtime.publish_message(MessageType(), topic_id=DefaultTopicId(type="other"))
    await runtime.stop_when_idle()

    assert agent_instance.num_calls == 2

    # Remove the subscription
    await runtime.remove_subscription(default_subscription.id)

    # Publish to the default topic
    runtime.start()
    await runtime.publish_message(MessageType(), topic_id=DefaultTopicId())
    await runtime.stop_when_idle()

    assert agent_instance.num_calls == 2

    # Publish to the other topic
    runtime.start()
    await runtime.publish_message(MessageType(), topic_id=DefaultTopicId(type="other"))
    await runtime.stop_when_idle()

    assert agent_instance.num_calls == 3

