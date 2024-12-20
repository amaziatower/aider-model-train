from __future__ import annotations

import asyncio
import inspect
import uuid
import warnings
from abc import ABC, abstractmethod
from asyncio import Future
from collections.abc import Sequence
from typing import Any, Awaitable, Callable, ClassVar, Dict, List, Mapping, Tuple, Type, TypeVar, final

from typing_extensions import Self

from autogen_core._types import (
    CancelledRpc,
    CancelRpc,
    CantHandleMessageResponse,
    RpcMessageDroppedResponse,
    RpcNoneResponse,
)
from autogen_core.exceptions import CantHandleException

from ._agent import Agent
from ._agent_id import AgentId
from ._agent_instantiation import AgentInstantiationContext
from ._agent_metadata import AgentMetadata
from ._agent_runtime import AgentRuntime
from ._agent_type import AgentType
from ._cancellation_token import CancellationToken
from ._message_context import MessageContext
from ._serialization import MessageSerializer, try_get_known_serializers_for_type
from ._subscription import Subscription, UnboundSubscription
from ._subscription_context import SubscriptionInstantiationContext
from ._topic import TopicId
from ._type_prefix_subscription import TypePrefixSubscription
from ._well_known_topics import (
    format_error_topic,
    format_rpc_request_topic,
    format_rpc_response_topic,
    is_error_message,
    is_rpc_cancel,
    is_rpc_request,
    is_rpc_response,
)

T = TypeVar("T", bound=Agent)

BaseAgentType = TypeVar("BaseAgentType", bound="BaseAgent")


# Decorator for adding an unbound subscription to an agent
def subscription_factory(subscription: UnboundSubscription) -> Callable[[Type[BaseAgentType]], Type[BaseAgentType]]:
    """:meta private:"""

    def decorator(cls: Type[BaseAgentType]) -> Type[BaseAgentType]:
        cls.internal_unbound_subscriptions_list.append(subscription)
        return cls

    return decorator


def handles(
    type: Type[Any], serializer: MessageSerializer[Any] | List[MessageSerializer[Any]] | None = None
) -> Callable[[Type[BaseAgentType]], Type[BaseAgentType]]:
    def decorator(cls: Type[BaseAgentType]) -> Type[BaseAgentType]:
        if serializer is None:
            serializer_list = try_get_known_serializers_for_type(type)
        else:
            serializer_list = [serializer] if not isinstance(serializer, Sequence) else serializer

        if len(serializer_list) == 0:
            raise ValueError(f"No serializers found for type {type}. Please provide an explicit serializer.")

        cls.internal_extra_handles_types.append((type, serializer_list))
        return cls

    return decorator


class BaseAgent(ABC, Agent):
    internal_unbound_subscriptions_list: ClassVar[List[UnboundSubscription]] = []
    """:meta private:"""
    internal_extra_handles_types: ClassVar[List[Tuple[Type[Any], List[MessageSerializer[Any]]]]] = []
    """:meta private:"""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Automatically set class_variable in each subclass so that they are not shared between subclasses
        cls.internal_extra_handles_types = []
        cls.internal_unbound_subscriptions_list = []

    @classmethod
    def _handles_types(cls) -> List[Tuple[Type[Any], List[MessageSerializer[Any]]]]:
        return cls.internal_extra_handles_types

    @classmethod
    def _unbound_subscriptions(cls) -> List[UnboundSubscription]:
        return cls.internal_unbound_subscriptions_list

    @property
    def metadata(self) -> AgentMetadata:
        assert self._id is not None
        return AgentMetadata(key=self._id.key, type=self._id.type, description=self._description)

    def __init__(self, description: str, *, forward_unbound_rpc_responses_to_handler: bool = False) -> None:
        """Base agent that all agents should inherit from. Puts in place assumed common functionality.

        Args:
            description (str): Description of the agent.
            forward_unbound_rpc_responses_to_handler (bool, optional): If an rpc request ID is not know to the agent, should the rpc request be forwarded to the handler. Defaults to False.

        Raises:
            RuntimeError: If the agent is not instantiated within the context of an AgentRuntime.
            ValueError: If there is an argument type error.
        """
        try:
            runtime = AgentInstantiationContext.current_runtime()
            id = AgentInstantiationContext.current_agent_id()
        except LookupError as e:
            raise RuntimeError(
                "BaseAgent must be instantiated within the context of an AgentRuntime. It cannot be directly instantiated."
            ) from e

        self._runtime: AgentRuntime = runtime
        self._id: AgentId = id
        if not isinstance(description, str):
            raise ValueError("Agent description must be a string")
        self._description = description
        self._pending_rpc_requests: Dict[str, Future[Any]] = {}
        self._self_rpc_handlers_in_progress: Dict[str, Future[Any]] = {}

        # TODO: find a way to clean this up over time.
        # Essentially, the reason for this existing is if a response is sent but we get an error back for that response
        # We need to forward this error back to the original sender, so they can fail their RPC.
        # Map of request_id -> (rpc_request_message_id, agent_type_of_rpc_sender)
        self._sent_rpc_responses: Dict[str, Tuple[str, str]] = {}
        self._forward_unbound_rpc_responses_to_handler = forward_unbound_rpc_responses_to_handler

    @property
    def type(self) -> str:
        return self.id.type

    @property
    def id(self) -> AgentId:
        return self._id

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    @abstractmethod
    async def on_message_impl(self, message: Any, ctx: MessageContext) -> None: ...

    @final
    async def on_message(self, message: Any, ctx: MessageContext) -> None:
        # Intercept errors for outstanding rpc requests, let the others pass through
        if (request_id := is_error_message(ctx.topic_id.type)) is not None:
            # Check if this error corresponds to an RPC response we have sent
            if request_id in self._sent_rpc_responses:
                # The recipient we were trying to send a response to never got this response, so we're going to send an error to them instead of the original message
                # If this message gets dropped, we're just going to ignore things
                original_rpc_request_message_id, agent_type_of_rpc_sender = self._sent_rpc_responses[request_id]
                error_topic = format_error_topic(
                    error_recipient_agent_type=agent_type_of_rpc_sender, request_id=original_rpc_request_message_id
                )
                await self.publish_message(
                    RpcMessageDroppedResponse(original_rpc_request_message_id), TopicId(error_topic, self.id.key)
                )
            # Check if we have a pending RPC that is error corresponds to
            elif request_id in self._pending_rpc_requests:
                self._pending_rpc_requests[request_id].set_exception(message)
                del self._pending_rpc_requests[request_id]
            else:
                await self.on_message_impl(message, ctx)

            return None

        # Intercept RPC cancel
        if (request_id := is_rpc_cancel(ctx.topic_id.type)) is not None:
            if request_id in self._self_rpc_handlers_in_progress:
                if isinstance(message, CancelRpc):
                    self._self_rpc_handlers_in_progress[request_id].cancel()
                    del self._self_rpc_handlers_in_progress[request_id]

            return None

        # Intercept RPC responses
        if (request_id := is_rpc_response(ctx.topic_id.type)) is not None:
            if request_id in self._pending_rpc_requests:
                if isinstance(message, RpcNoneResponse):
                    message = None
                if isinstance(message, CancelledRpc):
                    self._pending_rpc_requests[request_id].cancel()
                self._pending_rpc_requests[request_id].set_result(message)
                del self._pending_rpc_requests[request_id]
            elif self._forward_unbound_rpc_responses_to_handler:
                await self.on_message_impl(message, ctx)
            else:
                warnings.warn(
                    f"Received RPC response for unknown request {request_id}. To forward unbound rpc responses to the handler, set forward_unbound_rpc_responses_to_handler=True",
                    stacklevel=2,
                )
            return None

        try:
            await self.on_message_impl(message, ctx)
        # If the agent signalled it cannot handle this message, and it was an RPC request. Let's deliver this error to the RPC sender so they know.
        except CantHandleException:
            if (requestor_type := is_rpc_request(ctx.topic_id.type)) is not None:
                error_topic = format_error_topic(error_recipient_agent_type=requestor_type, request_id=ctx.message_id)
                await self.publish_message(
                    CantHandleMessageResponse(message_id=ctx.message_id), TopicId(error_topic, self.id.key)
                )
            else:
                raise

    async def send_message(
        self,
        message: Any,
        recipient: AgentId,
        *,
        cancellation_token: CancellationToken | None = None,
        timeout: float | None = None,
    ) -> Any:
        """See :py:meth:`autogen_core.AgentRuntime.send_message` for more information."""
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        recipient_topic = TopicId(
            type=format_rpc_request_topic(rpc_recipient_agent_type=recipient.type, rpc_sender_agent_type=self.id.type),
            source=recipient.key,
        )
        request_id = str(uuid.uuid4())

        future = Future[Any]()

        await self._runtime.publish_message(
            message,
            sender=self.id,
            topic_id=recipient_topic,
            cancellation_token=cancellation_token,
            message_id=request_id,
        )

        self._pending_rpc_requests[request_id] = future

        async with asyncio.timeout(timeout):
            return await future

    async def _rpc_response(self, handler_return_value: Any, ctx: MessageContext) -> None:
        if (requestor_type := is_rpc_request(ctx.topic_id.type)) is not None:
            if handler_return_value is None:
                handler_return_value = RpcNoneResponse()

            response_topic_id = TopicId(
                type=format_rpc_response_topic(rpc_sender_agent_type=requestor_type, request_id=ctx.message_id),
                source=self.id.key,
            )
            message_id = str(uuid.uuid4())
            # Intentionally accessing a private attribute here
            # We store this so that if the response is dropped, we can send an error to the client instead.
            # request_id -> (rpc_request_message_id, agent_type_of_rpc_sender)
            self._sent_rpc_responses[message_id] = (ctx.message_id, requestor_type)  # type: ignore

            await self.publish_message(
                message=handler_return_value,
                topic_id=response_topic_id,
                cancellation_token=ctx.cancellation_token,
                message_id=message_id,
            )

    async def publish_message(
        self,
        message: Any,
        topic_id: TopicId,
        *,
        cancellation_token: CancellationToken | None = None,
        message_id: str | None = None,
    ) -> None:
        await self._runtime.publish_message(
            message, topic_id, sender=self.id, cancellation_token=cancellation_token, message_id=message_id
        )

    async def save_state(self) -> Mapping[str, Any]:
        warnings.warn("save_state not implemented", stacklevel=2)
        return {}

    async def load_state(self, state: Mapping[str, Any]) -> None:
        warnings.warn("load_state not implemented", stacklevel=2)
        pass

    @classmethod
    async def register(
        cls,
        runtime: AgentRuntime,
        type: str,
        factory: Callable[[], Self | Awaitable[Self]],
        *,
        skip_class_subscriptions: bool = False,
        skip_direct_message_subscription: bool = False,
    ) -> AgentType:
        agent_type = AgentType(type)
        agent_type = await runtime.register_factory(type=agent_type, agent_factory=factory, expected_class=cls)
        if not skip_class_subscriptions:
            with SubscriptionInstantiationContext.populate_context(agent_type):
                subscriptions: List[Subscription] = []
                for unbound_subscription in cls._unbound_subscriptions():
                    subscriptions_list_result = unbound_subscription()
                    if inspect.isawaitable(subscriptions_list_result):
                        subscriptions_list = await subscriptions_list_result
                    else:
                        subscriptions_list = subscriptions_list_result

                    subscriptions.extend(subscriptions_list)
            for subscription in subscriptions:
                await runtime.add_subscription(subscription)

        if not skip_direct_message_subscription:
            # Additionally adds a special prefix subscription for this agent to receive direct messages
            await runtime.add_subscription(
                TypePrefixSubscription(
                    # The prefix MUST include ":" to avoid collisions with other agents
                    topic_type_prefix=agent_type.type + ":",
                    agent_type=agent_type.type,
                )
            )

        # TODO: deduplication
        for _message_type, serializer in cls._handles_types():
            runtime.add_message_serializer(serializer)

        return agent_type
