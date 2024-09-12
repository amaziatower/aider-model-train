import logging
import warnings
from functools import wraps
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Literal,
    Protocol,
    Sequence,
    Type,
    TypeVar,
    cast,
    get_type_hints,
    overload,
    runtime_checkable,
)

from autogen_core.base import try_get_known_serializers_for_type

from ..base import MESSAGE_TYPE_REGISTRY, BaseAgent, MessageContext
from ..base.exceptions import CantHandleException
from ._type_helpers import AnyType, get_types

logger = logging.getLogger("autogen_core")

ReceivesT = TypeVar("ReceivesT")
ProducesT = TypeVar("ProducesT", covariant=True)

# TODO: Generic typevar bound binding U to agent type
# Can't do because python doesnt support it


# Pyright and mypy disagree on the variance of ReceivesT. Mypy thinks it should be contravariant here.
# Revisit this later to see if we can remove the ignore.
@runtime_checkable
class MessageHandler(Protocol[ReceivesT, ProducesT]):  # type: ignore
    target_types: Sequence[type]
    produces_types: Sequence[type]
    is_message_handler: Literal[True]
    router: Callable[[ReceivesT, MessageContext], bool]

    async def __call__(self, message: ReceivesT, ctx: MessageContext) -> ProducesT: ...


# NOTE: this works on concrete types and not inheritance
# TODO: Use a protocl for the outer function to check checked arg names


@overload
def message_handler(
    func: Callable[[Any, ReceivesT, MessageContext], Coroutine[Any, Any, ProducesT]],
) -> MessageHandler[ReceivesT, ProducesT]: ...


@overload
def message_handler(
    func: None = None,
    *,
    match: None = ...,
    strict: bool = ...,
) -> Callable[
    [Callable[[Any, ReceivesT, MessageContext], Coroutine[Any, Any, ProducesT]]],
    MessageHandler[ReceivesT, ProducesT],
]: ...


@overload
def message_handler(
    func: None = None,
    *,
    match: Callable[[ReceivesT, MessageContext], bool],
    strict: bool = ...,
) -> Callable[
    [Callable[[Any, ReceivesT, MessageContext], Coroutine[Any, Any, ProducesT]]],
    MessageHandler[ReceivesT, ProducesT],
]: ...


def message_handler(
    func: None | Callable[[Any, ReceivesT, MessageContext], Coroutine[Any, Any, ProducesT]] = None,
    *,
    strict: bool = True,
    match: None | Callable[[ReceivesT, MessageContext], bool] = None,
) -> (
    Callable[
        [Callable[[Any, ReceivesT, MessageContext], Coroutine[Any, Any, ProducesT]]],
        MessageHandler[ReceivesT, ProducesT],
    ]
    | MessageHandler[ReceivesT, ProducesT]
):
    """Decorator for message handlers.

    Add this decorator to methods in a :class:`RoutedAgent` class that are intended to handle messages.
    These methods must have a specific signature that needs to be followed for it to be valid:

    - The method must be an `async` method.
    - The method must be decorated with the `@message_handler` decorator.
    - The method must have exactly 3 arguments:
        1. `self`
        2. `message`: The message to be handled, this must be type-hinted with the message type that it is intended to handle.
        3. `ctx`: A :class:`autogen_core.base.MessageContext` object.
    - The method must be type hinted with what message types it can return as a response, or it can return `None` if it does not return anything.

    Handlers can handle more than one message type by accepting a Union of the message types. It can also return more than one message type by returning a Union of the message types.

    Args:
        func: The function to be decorated.
        strict: If `True`, the handler will raise an exception if the message type or return type is not in the target types. If `False`, it will log a warning instead.
        match: A function that takes the message and the context as arguments and returns a boolean. This is used for secondary routing after the message type. For handlers addressing the same message type, the match function is applied in alphabetical order of the handlers and the first matching handler will be called while the rest are skipped. If `None`, the first handler in alphabetical order matching the same message type will be called.
    """

    def decorator(
        func: Callable[[Any, ReceivesT, MessageContext], Coroutine[Any, Any, ProducesT]],
    ) -> MessageHandler[ReceivesT, ProducesT]:
        type_hints = get_type_hints(func)
        if "message" not in type_hints:
            raise AssertionError("message parameter not found in function signature")

        if "return" not in type_hints:
            raise AssertionError("return not found in function signature")

        # Get the type of the message parameter
        target_types = get_types(type_hints["message"])
        if target_types is None:
            raise AssertionError("Message type not found")

        # print(type_hints)
        return_types = get_types(type_hints["return"])

        if return_types is None:
            raise AssertionError("Return type not found")

        # Convert target_types to list and stash

        @wraps(func)
        async def wrapper(self: Any, message: ReceivesT, ctx: MessageContext) -> ProducesT:
            if type(message) not in target_types:
                if strict:
                    raise CantHandleException(f"Message type {type(message)} not in target types {target_types}")
                else:
                    logger.warning(f"Message type {type(message)} not in target types {target_types}")

            return_value = await func(self, message, ctx)

            if AnyType not in return_types and type(return_value) not in return_types:
                if strict:
                    raise ValueError(f"Return type {type(return_value)} not in return types {return_types}")
                else:
                    logger.warning(f"Return type {type(return_value)} not in return types {return_types}")

            return return_value

        wrapper_handler = cast(MessageHandler[ReceivesT, ProducesT], wrapper)
        wrapper_handler.target_types = list(target_types)
        wrapper_handler.produces_types = list(return_types)
        wrapper_handler.is_message_handler = True
        wrapper_handler.router = match or (lambda _message, _ctx: True)

        return wrapper_handler

    if func is None and not callable(func):
        return decorator
    elif callable(func):
        return decorator(func)
    else:
        raise ValueError("Invalid arguments")


class RoutedAgent(BaseAgent):
    """A base class for agents that route messages to handlers based on the type of the message
    and optional matching functions.

    To create a routed agent, subclass this class and add message handlers as methods decorated with
    the :func:`message_handler` decorator.

    Example:

    .. code-block:: python

        from autogen_core.base import MessageContext
        from autogen_core.components import RoutedAgent, message_handler
        # Assume Message, MessageWithContent, and Response are defined elsewhere.


        class MyAgent(RoutedAgent):
            def __init__(self):
                super().__init__("MyAgent")

            @message_handler
            async def handle_message(self, message: Message, ctx: MessageContext) -> Response:
                return Response()

            @message_handler(match=lambda message, ctx: message.content == "special")
            async def handle_special_message(self, message: MessageWithContent, ctx: MessageContext) -> Response:
                return Response()
    """

    def __init__(self, description: str) -> None:
        # Self is already bound to the handlers
        self._handlers: Dict[
            Type[Any],
            List[MessageHandler[Any, Any]],
        ] = {}

        # Iterate over all attributes in alphabetical order and find message handlers.
        for attr in dir(self):
            if callable(getattr(self, attr, None)):
                handler = getattr(self, attr)
                if hasattr(handler, "is_message_handler"):
                    message_handler = cast(MessageHandler[Any, Any], handler)
                    for target_type in message_handler.target_types:
                        self._handlers.setdefault(target_type, []).append(message_handler)

        for message_type in self._handlers.keys():
            for serializer in try_get_known_serializers_for_type(message_type):
                MESSAGE_TYPE_REGISTRY.add_serializer(serializer)

        super().__init__(description)

    async def on_message(self, message: Any, ctx: MessageContext) -> Any | None:
        """Handle a message by routing it to the appropriate message handler.
        Do not override this method in subclasses. Instead, add message handlers as methods decorated with
        the :func:`message_handler` decorator."""
        key_type: Type[Any] = type(message)  # type: ignore
        handlers = self._handlers.get(key_type)  # type: ignore
        if handlers is not None:
            # Iterate over all handlers for this matching message type.
            # Call the first handler whose router returns True and then return the result.
            for h in handlers:
                if h.router(message, ctx):
                    return await h(message, ctx)
        return await self.on_unhandled_message(message, ctx)  # type: ignore

    async def on_unhandled_message(self, message: Any, ctx: MessageContext) -> None:
        """Called when a message is received that does not have a matching message handler.
        The default implementation logs an info message."""
        logger.info(f"Unhandled message: {message}")


# Deprecation warning for TypeRoutedAgent
class TypeRoutedAgent(RoutedAgent):
    """Deprecated. Use :class:`RoutedAgent` instead."""

    def __init__(self, description: str) -> None:
        warnings.warn("TypeRoutedAgent is deprecated. Use RoutedAgent instead.", DeprecationWarning, stacklevel=2)
        super().__init__(description)
