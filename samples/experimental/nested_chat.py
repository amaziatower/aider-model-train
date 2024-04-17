import asyncio
import pprint
from typing import List

import aioconsole

from autogen.experimental import TwoAgentChat
from autogen.experimental.agent import Agent
from autogen.experimental.agents.chat_agent import ChatAgent
from autogen.experimental.agents.user_input_agent import UserInputAgent
from autogen.experimental.chat_histories.chat_history_list import ChatHistoryList
from autogen.experimental.chat_history import ChatHistoryReadOnly
from autogen.experimental.chats.group_chat import GroupChat
from autogen.experimental.drivers import run_in_terminal
from autogen.experimental.speaker_selections.round_robin_speaker_selection import RoundRobin
from autogen.experimental.termination import (
    NotTerminated,
    Terminated,
    Termination,
    TerminationReason,
    TerminationResult,
)
from autogen.experimental.types import AssistantMessage, GenerateReplyResult, Message, UserMessage


class FibTermination(Termination):
    def record_turn_taken(self, agent: Agent) -> None:
        pass

    async def check_termination(self, chat_history: ChatHistoryReadOnly) -> TerminationResult:
        assert len(chat_history) > 0
        message = chat_history.messages[0]
        assert isinstance(message, UserMessage) and isinstance(message.content, str)
        desired_fib_number = int(message.content)
        if len(chat_history) == 1 + desired_fib_number:
            return Terminated(reason=TerminationReason.GOAL_REACHED, explanation="Fib number reached")
        return NotTerminated()

    def reset(self) -> None:
        pass


class FibbonacciAgent(Agent):
    @property
    def name(self) -> str:
        """Get the name of the agent."""
        return "fib"

    @property
    def description(self) -> str:
        """Get the description of the agent."""
        return "Blah"

    async def generate_reply(
        self,
        chat_history: ChatHistoryReadOnly,
    ) -> GenerateReplyResult:
        messages_to_use: List[Message] = []
        if len(chat_history) > 1:
            messages_to_use = list(chat_history.messages[1:])

        if len(messages_to_use) == 0:
            num1 = AssistantMessage(content="1")
            num2 = AssistantMessage(content="0")
        elif len(messages_to_use) == 1:
            num1 = AssistantMessage(content="0")
            num2 = messages_to_use[-1]  # type: ignore
        else:
            num1, num2 = messages_to_use[-2], messages_to_use[-1]  # type: ignore

        assert isinstance(num1, AssistantMessage)
        assert isinstance(num1.content, str)
        assert isinstance(num2, AssistantMessage)
        assert isinstance(num2.content, str)
        num1_int = int(num1.content)
        num2_int = int(num2.content)
        return AssistantMessage(content=str(num1_int + num2_int))


async def user_input(prompt: str) -> str:
    res = await aioconsole.ainput("How many fib numbers to generate?")  # type: ignore
    if not isinstance(res, str):
        raise ValueError("Expected a string")

    try:
        int(res)
    except ValueError:
        return ""

    return res


def prime_nested_chat(input: ChatHistoryReadOnly) -> ChatHistoryReadOnly:
    conversation = ChatHistoryList()
    conversation.append_message(input.messages[-1], input.contexts[-1])
    return conversation


async def main() -> None:

    human = UserInputAgent(name="user", human_input_callback=user_input)
    fib_chat = GroupChat(
        agents=[FibbonacciAgent()],
        send_introduction=False,
        speaker_selection=RoundRobin(),
        termination_manager=FibTermination(),
    )

    nested_chat = ChatAgent(name="nested_chat", chat=fib_chat, input_transform=prime_nested_chat)

    chat = TwoAgentChat(human, nested_chat)

    await run_in_terminal(chat)
    output = pprint.pformat(chat.chat_history.contexts)
    await aioconsole.aprint(output)  # type: ignore


if __name__ == "__main__":
    asyncio.run(main())
