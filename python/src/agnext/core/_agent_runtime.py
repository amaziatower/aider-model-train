from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable, Mapping, Protocol, TypeVar, overload, runtime_checkable

from ._agent import Agent
from ._agent_id import AgentId
from ._agent_metadata import AgentMetadata
from ._agent_proxy import AgentProxy
from ._cancellation_token import CancellationToken

# Undeliverable - error

T = TypeVar("T", bound=Agent)

agent_instantiation_context: ContextVar[tuple[AgentRuntime, AgentId]] = ContextVar("agent_instantiation_context")


@runtime_checkable
class AgentRuntime(Protocol):
    async def send_message(
        self,
        message: Any,
        recipient: AgentId,
        *,
        sender: AgentId | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> Any:
        """Send a message to an agent and get a response.

        Args:
            message (Any): The message to send.
            recipient (AgentId): The agent to send the message to.
            sender (AgentId | None, optional): Agent which sent the message. Should **only** be None if this was sent from no agent, such as directly to the runtime externally. Defaults to None.
            cancellation_token (CancellationToken | None, optional): Token used to cancel an in progress . Defaults to None.

        Raises:
            CantHandleException: If the recipient cannot handle the message.
            UndeliverableException: If the message cannot be delivered.
            Other: Any other exception raised by the recipient.

        Returns:
            Any: The response from the agent.
        """

        ...

    async def publish_message(
        self,
        message: Any,
        *,
        namespace: str | None = None,
        sender: AgentId | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        """Publish a message to all agents in the given namespace, or if no namespace is provided, the namespace of the sender.

        No responses are expected from publishing.

        Args:
            message (Any): The message to publish.
            namespace (str | None, optional): The namespace to publish to. Defaults to None.
            sender (AgentId | None, optional): The agent which sent the message. Defaults to None.
            cancellation_token (CancellationToken | None, optional): Token used to cancel an in progress . Defaults to None.

        Raises:
            UndeliverableException: If the message cannot be delivered.
        """

    @overload
    def register(
        self,
        name: str,
        agent_factory: Callable[[], T],
    ) -> None: ...

    @overload
    def register(
        self,
        name: str,
        agent_factory: Callable[[AgentRuntime, AgentId], T],
    ) -> None: ...

    def register(
        self,
        name: str,
        agent_factory: Callable[[], T] | Callable[[AgentRuntime, AgentId], T],
    ) -> None:
        """Register an agent factory with the runtime associated with a specific name. The name must be unique.

        Args:
            name (str): The name of the type agent this factory creates.
            agent_factory (Callable[[], T] | Callable[[AgentRuntime, AgentId], T]): The factory that creates the agent, where T is a concrete Agent type.


        Example:
            .. code-block:: python

                runtime.register(
                    "chat_agent",
                    lambda: ChatCompletionAgent(
                        description="A generic chat agent.",
                        system_messages=[SystemMessage("You are a helpful assistant")],
                        model_client=OpenAIChatCompletionClient(model="gpt-4o"),
                        memory=BufferedChatMemory(buffer_size=10),
                    ),
                )

        """

        ...

    def get(self, name: str, *, namespace: str = "default") -> AgentId:
        """Get an agent by name and namespace.

        Args:
            name (str): The name of the agent.
            namespace (str, optional): The namespace of the agent. Defaults to "default".

        Returns:
            AgentId: The agent id.
        """
        ...

    def get_proxy(self, name: str, *, namespace: str = "default") -> AgentProxy:
        """Get a proxy for an agent by name and namespace.

        Args:
            name (str): The name of the agent.
            namespace (str, optional): The namespace of the agent. Defaults to "default".

        Returns:
            AgentProxy: The agent proxy.
        """
        ...

    @overload
    def register_and_get(
        self,
        name: str,
        agent_factory: Callable[[], T],
        *,
        namespace: str = "default",
    ) -> AgentId: ...

    @overload
    def register_and_get(
        self,
        name: str,
        agent_factory: Callable[[AgentRuntime, AgentId], T],
        *,
        namespace: str = "default",
    ) -> AgentId: ...

    def register_and_get(
        self,
        name: str,
        agent_factory: Callable[[], T] | Callable[[AgentRuntime, AgentId], T],
        *,
        namespace: str = "default",
    ) -> AgentId:
        """Register an agent factory with the runtime associated with a specific name and get the agent id. The name must be unique.

        Args:
            name (str): The name of the type agent this factory creates.
            agent_factory (Callable[[], T] | Callable[[AgentRuntime, AgentId], T]): The factory that creates the agent, where T is a concrete Agent type.
            namespace (str, optional): The namespace of the agent. Defaults to "default".

        Returns:
            AgentId: The agent id.
        """
        self.register(name, agent_factory)
        return self.get(name, namespace=namespace)

    @overload
    def register_and_get_proxy(
        self,
        name: str,
        agent_factory: Callable[[], T],
        *,
        namespace: str = "default",
    ) -> AgentProxy: ...

    @overload
    def register_and_get_proxy(
        self,
        name: str,
        agent_factory: Callable[[AgentRuntime, AgentId], T],
        *,
        namespace: str = "default",
    ) -> AgentProxy: ...

    def register_and_get_proxy(
        self,
        name: str,
        agent_factory: Callable[[], T] | Callable[[AgentRuntime, AgentId], T],
        *,
        namespace: str = "default",
    ) -> AgentProxy:
        """Register an agent factory with the runtime associated with a specific name and get the agent proxy. The name must be unique.

        Args:
            name (str): The name of the type agent this factory creates.
            agent_factory (Callable[[], T] | Callable[[AgentRuntime, AgentId], T]): The factory that creates the agent, where T is a concrete Agent type.
            namespace (str, optional): The namespace of the agent. Defaults to "default".

        Returns:
            AgentProxy: The agent proxy.
        """
        self.register(name, agent_factory)
        return self.get_proxy(name, namespace=namespace)

    def save_state(self) -> Mapping[str, Any]:
        """Save the state of the entire runtime, including all hosted agents. The only way to restore the state is to pass it to :meth:`load_state`.

        The structure of the state is implementation defined and can be any JSON serializable object.

        Returns:
            Mapping[str, Any]: The saved state.
        """
        ...

    def load_state(self, state: Mapping[str, Any]) -> None:
        """Load the state of the entire runtime, including all hosted agents. The state should be the same as the one returned by :meth:`save_state`.

        Args:
            state (Mapping[str, Any]): The saved state.
        """
        ...

    def agent_metadata(self, agent: AgentId) -> AgentMetadata:
        """Get the metadata for an agent.

        Args:
            agent (AgentId): The agent id.

        Returns:
            AgentMetadata: The agent metadata.
        """
        ...

    def agent_save_state(self, agent: AgentId) -> Mapping[str, Any]:
        """Save the state of a single agent.

        The structure of the state is implementation defined and can be any JSON serializable object.

        Args:
            agent (AgentId): The agent id.

        Returns:
            Mapping[str, Any]: The saved state.
        """
        ...

    def agent_load_state(self, agent: AgentId, state: Mapping[str, Any]) -> None:
        """Load the state of a single agent.

        Args:
            agent (AgentId): The agent id.
            state (Mapping[str, Any]): The saved state.
        """
        ...
