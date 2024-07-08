import warnings
from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

from ._agent import Agent
from ._agent_id import AgentId
from ._agent_metadata import AgentMetadata
from ._agent_runtime import AgentRuntime, agent_instantiation_context
from ._cancellation_token import CancellationToken


class BaseAgent(ABC, Agent):
    @property
    def metadata(self) -> AgentMetadata:
        assert self._id is not None
        return AgentMetadata(
            namespace=self._id.namespace,
            name=self._id.name,
            description=self._description,
            subscriptions=self._subscriptions,
        )

    def __init__(self, description: str, subscriptions: Sequence[str]) -> None:
        try:
            runtime, id = agent_instantiation_context.get()
        except LookupError as e:
            raise RuntimeError(
                "BaseAgent must be instantiated within the context of an AgentRuntime. It cannot be directly instantiated."
            ) from e

        self._runtime: AgentRuntime = runtime
        self._id: AgentId = id
        self._description = description
        self._subscriptions = subscriptions

    @property
    def name(self) -> str:
        return self.id.name

    @property
    def id(self) -> AgentId:
        return self._id

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    @abstractmethod
    async def on_message(self, message: Any, cancellation_token: CancellationToken) -> Any: ...

    async def send_message(
        self,
        message: Any,
        recipient: AgentId,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> Any:
        """See :py:meth:`agnext.core.AgentRuntime.send_message` for more information."""
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        return await self._runtime.send_message(
            message,
            sender=self.id,
            recipient=recipient,
            cancellation_token=cancellation_token,
        )

    async def publish_message(
        self,
        message: Any,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        await self._runtime.publish_message(message, sender=self.id, cancellation_token=cancellation_token)

    def save_state(self) -> Mapping[str, Any]:
        warnings.warn("save_state not implemented", stacklevel=2)
        return {}

    def load_state(self, state: Mapping[str, Any]) -> None:
        warnings.warn("load_state not implemented", stacklevel=2)
        pass
