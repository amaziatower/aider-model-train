import asyncio
from asyncio import Future
from dataclasses import dataclass
from typing import Awaitable, Dict, Generic, List, Set, Type, TypeVar

from agnext.core.cancellation_token import CancellationToken

from ..core.agent import Agent
from ..core.agent_runtime import AgentRuntime

T = TypeVar("T")


@dataclass
class BroadcastMessageEnvelope(Generic[T]):
    """A message envelope for broadcasting messages to all agents that can handle
    the message of the type T."""

    message: T
    future: Future[List[T]]
    cancellation_token: CancellationToken


@dataclass
class SendMessageEnvelope(Generic[T]):
    """A message envelope for sending a message to a specific agent that can handle
    the message of the type T."""

    message: T
    destination: Agent[T]
    future: Future[T]
    cancellation_token: CancellationToken


@dataclass
class ResponseMessageEnvelope(Generic[T]):
    """A message envelope for sending a response to a message."""

    message: T
    future: Future[T]


@dataclass
class BroadcastResponseMessageEnvelope(Generic[T]):
    """A message envelope for sending a response to a message."""

    message: List[T]
    future: Future[List[T]]


class SingleThreadedAgentRuntime(AgentRuntime[T]):
    def __init__(self) -> None:
        self._message_queue: List[
            BroadcastMessageEnvelope[T]
            | SendMessageEnvelope[T]
            | ResponseMessageEnvelope[T]
            | BroadcastResponseMessageEnvelope[T]
        ] = []
        self._per_type_subscribers: Dict[Type[T], List[Agent[T]]] = {}
        self._agents: Set[Agent[T]] = set()

    def add_agent(self, agent: Agent[T]) -> None:
        for message_type in agent.subscriptions:
            if message_type not in self._per_type_subscribers:
                self._per_type_subscribers[message_type] = []
            self._per_type_subscribers[message_type].append(agent)
        self._agents.add(agent)

    # Returns the response of the message
    def send_message(
        self, message: T, destination: Agent[T], cancellation_token: CancellationToken | None = None
    ) -> Future[T]:
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        loop = asyncio.get_event_loop()
        future: Future[T] = loop.create_future()

        self._message_queue.append(SendMessageEnvelope(message, destination, future, cancellation_token))

        return future

    # Returns the response of all handling agents
    def broadcast_message(self, message: T, cancellation_token: CancellationToken | None = None) -> Future[List[T]]:
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        future: Future[List[T]] = asyncio.get_event_loop().create_future()
        self._message_queue.append(BroadcastMessageEnvelope(message, future, cancellation_token))
        return future

    async def _process_send(self, message_envelope: SendMessageEnvelope[T]) -> None:
        recipient = message_envelope.destination
        if recipient not in self._agents:
            message_envelope.future.set_exception(Exception("Recipient not found"))
            return

        try:
            response = await recipient.on_message(
                message_envelope.message, cancellation_token=message_envelope.cancellation_token
            )
        except BaseException as e:
            message_envelope.future.set_exception(e)
            return

        self._message_queue.append(ResponseMessageEnvelope(response, message_envelope.future))

    async def _process_broadcast(self, message_envelope: BroadcastMessageEnvelope[T]) -> None:
        responses: List[Awaitable[T]] = []
        for agent in self._per_type_subscribers.get(type(message_envelope.message), []):
            future = agent.on_message(message_envelope.message, cancellation_token=message_envelope.cancellation_token)
            responses.append(future)

        try:
            all_responses = await asyncio.gather(*responses)
        except BaseException as e:
            message_envelope.future.set_exception(e)
            return

        self._message_queue.append(BroadcastResponseMessageEnvelope(all_responses, message_envelope.future))

    async def _process_response(self, message_envelope: ResponseMessageEnvelope[T]) -> None:
        message_envelope.future.set_result(message_envelope.message)

    async def _process_broadcast_response(self, message_envelope: BroadcastResponseMessageEnvelope[T]) -> None:
        message_envelope.future.set_result(message_envelope.message)

    async def process_next(self) -> None:
        if len(self._message_queue) == 0:
            # Yield control to the event loop to allow other tasks to run
            await asyncio.sleep(0)
            return

        message_envelope = self._message_queue.pop(0)

        match message_envelope:
            case SendMessageEnvelope(message, destination, future, cancellation_token):
                asyncio.create_task(
                    self._process_send(SendMessageEnvelope(message, destination, future, cancellation_token))
                )
            case BroadcastMessageEnvelope(message, future, cancellation_token):
                asyncio.create_task(
                    self._process_broadcast(BroadcastMessageEnvelope(message, future, cancellation_token))
                )
            case ResponseMessageEnvelope(message, future):
                asyncio.create_task(self._process_response(ResponseMessageEnvelope(message, future)))
            case BroadcastResponseMessageEnvelope(message, future):
                asyncio.create_task(self._process_broadcast_response(BroadcastResponseMessageEnvelope(message, future)))

        # Yield control to the message loop to allow other tasks to run
        await asyncio.sleep(0)
