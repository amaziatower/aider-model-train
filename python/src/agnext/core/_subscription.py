from typing import Protocol, runtime_checkable

from agnext.core import AgentId

from ._topic import TopicId


@runtime_checkable
class Subscription(Protocol):
    """Subscriptions define the topics that an agent is interested in."""

    @property
    def id(self) -> str:
        """Get the ID of the subscription.

        Implementations should return a unique ID for the subscription. Usually this is a UUID.

        Returns:
            str: ID of the subscription.
        """
        ...

    def __eq__(self, other: object) -> bool:
        """Check if two subscriptions are equal.

        Args:
            other (object): Other subscription to compare against.

        Returns:
            bool: True if the subscriptions are equal, False otherwise.
        """
        if not isinstance(other, Subscription):
            return False

        return self.id == other.id

    def is_match(self, topic_id: TopicId) -> bool:
        """Check if a given topic_id matches the subscription.

        Args:
            topic_id (TopicId): TopicId to check.

        Returns:
            bool: True if the topic_id matches the subscription, False otherwise.
        """
        ...

    def map_to_agent(self, topic_id: TopicId) -> AgentId:
        """Map a topic_id to an agent. Should only be called if `is_match` returns True for the given topic_id.

        Args:
            topic_id (TopicId): TopicId to map.

        Returns:
            AgentId: ID of the agent that should handle the topic_id.

        Raises:
            CantHandleException: If the subscription cannot handle the topic_id.
        """
        ...
