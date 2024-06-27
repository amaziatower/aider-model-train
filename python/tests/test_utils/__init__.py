from dataclasses import dataclass
from typing import Any

from agnext.components import TypeRoutedAgent, message_handler
from agnext.core import CancellationToken, BaseAgent


@dataclass
class MessageType:
    ...

@dataclass
class CascadingMessageType:
    round: int

class LoopbackAgent(TypeRoutedAgent):
    def __init__(self) -> None:
        super().__init__("A loop back agent.")
        self.num_calls = 0


    @message_handler
    async def on_new_message(self, message: MessageType, cancellation_token: CancellationToken) -> MessageType:
        self.num_calls += 1
        return message


class CascadingAgent(TypeRoutedAgent):

    def __init__(self, max_rounds: int) -> None:
        super().__init__("A cascading agent.")
        self.num_calls = 0
        self.max_rounds = max_rounds
    
    @message_handler
    async def on_new_message(self, message: CascadingMessageType, cancellation_token: CancellationToken) -> None:
        self.num_calls += 1
        if message.round == self.max_rounds:
            return
        await self.publish_message(CascadingMessageType(round=message.round + 1))

class NoopAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("A no op agent", [])

    async def on_message(self, message: Any, cancellation_token: CancellationToken) -> Any:
        raise NotImplementedError
