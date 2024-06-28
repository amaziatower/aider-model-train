import inspect
from typing import Any, Awaitable, Callable, Mapping, Sequence, TypeVar, get_type_hints

from ..core._agent import Agent
from ..core._agent_id import AgentId
from ..core._agent_metadata import AgentMetadata
from ..core._agent_runtime import AgentRuntime, agent_instantiation_context
from ..core._cancellation_token import CancellationToken
from ..core.exceptions import CantHandleException
from ._type_helpers import get_types

T = TypeVar("T")


def get_subscriptions_from_closure(
    closure: Callable[[AgentRuntime, AgentId, T, CancellationToken], Awaitable[Any]],
) -> Sequence[type]:
    args = inspect.getfullargspec(closure)[0]
    if len(args) != 4:
        raise AssertionError("Closure must have 4 arguments")

    message_arg_name = args[2]

    type_hints = get_type_hints(closure)

    if "return" not in type_hints:
        raise AssertionError("return not found in function signature")

    # Get the type of the message parameter
    target_types = get_types(type_hints[message_arg_name])
    if target_types is None:
        raise AssertionError("Message type not found")

    # print(type_hints)
    return_types = get_types(type_hints["return"])

    if return_types is None:
        raise AssertionError("Return type not found")

    return target_types


class ClosureAgent(Agent):
    def __init__(
        self, description: str, closure: Callable[[AgentRuntime, AgentId, T, CancellationToken], Awaitable[Any]]
    ) -> None:
        try:
            runtime, id = agent_instantiation_context.get()
        except LookupError as e:
            raise RuntimeError(
                "ClosureAgent must be instantiated within the context of an AgentRuntime. It cannot be directly instantiated."
            ) from e

        self._runtime: AgentRuntime = runtime
        self._id: AgentId = id
        self._description = description
        self._subscriptions = get_subscriptions_from_closure(closure)
        self._closure = closure

    @property
    def metadata(self) -> AgentMetadata:
        assert self._id is not None
        return AgentMetadata(
            namespace=self._id.namespace,
            name=self._id.name,
            description=self._description,
            subscriptions=self._subscriptions,
        )

    @property
    def name(self) -> str:
        return self.id.name

    @property
    def id(self) -> AgentId:
        return self._id

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    async def on_message(self, message: Any, cancellation_token: CancellationToken) -> Any:
        if type(message) not in self._subscriptions:
            raise CantHandleException(
                f"Message type {type(message)} not in target types {self._subscriptions} of {self.id}"
            )
        return await self._closure(self._runtime, self._id, message, cancellation_token)

    def save_state(self) -> Mapping[str, Any]:
        raise ValueError("save_state not implemented for ClosureAgent")

    def load_state(self, state: Mapping[str, Any]) -> None:
        raise ValueError("load_state not implemented for ClosureAgent")
