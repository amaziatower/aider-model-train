"""
This example shows how to use publish-subscribe to implement
a simple interaction between a coder and an executor agent.
1. The coder agent receives a task message, generates a code block,
and publishes a code execution
task message.
2. The executor agent receives the code execution task message,
executes the code block, and publishes a code execution task result message.
3.  The coder agent receives the code execution task result message, depending
on the result: if the task is completed, it publishes a task completion message;
otherwise, it generates a new code block and publishes a code execution task message.
4. The process continues until the coder agent publishes a task completion message.
5. The termination handler listens for the task completion message and when it is
received, it sets the termination flag to True, and the main function
terminates the process.
"""

import asyncio
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

from agnext.application import SingleThreadedAgentRuntime
from agnext.components import TypeRoutedAgent, message_handler
from agnext.components.code_executor import CodeBlock, CodeExecutor, LocalCommandLineCodeExecutor
from agnext.components.models import (
    AssistantMessage,
    ChatCompletionClient,
    LLMMessage,
    OpenAIChatCompletionClient,
    SystemMessage,
    UserMessage,
)
from agnext.core import AgentId, CancellationToken
from agnext.core.intervention import DefaultInterventionHandler


@dataclass
class TaskMessage:
    content: str


@dataclass
class TaskCompletion:
    content: str


@dataclass
class CodeExecutionTask:
    session_id: str
    content: str


@dataclass
class CodeExecutionTaskResult:
    session_id: str
    output: str
    exit_code: int


class Coder(TypeRoutedAgent):
    """An agent that writes code."""

    def __init__(
        self,
        model_client: ChatCompletionClient,
    ) -> None:
        super().__init__(description="A Python coder assistant.")
        self._model_client = model_client
        self._system_messages = [
            SystemMessage(
                """You are a helpful AI assistant.
Solve tasks using your coding and language skills.
In the following cases, suggest python code (in a python coding block) or shell script (in a sh coding block) for the user to execute.
    1. When you need to collect info, use the code to output the info you need, for example, browse or search the web, download/read a file, print the content of a webpage or a file, get the current date/time, check the operating system. After sufficient info is printed and the task is ready to be solved based on your language skill, you can solve the task by yourself.
    2. When you need to perform some task with code, use the code to perform the task and output the result. Finish the task smartly.
Solve the task step by step if you need to. If a plan is not provided, explain your plan first. Be clear which step uses code, and which step uses your language skill.
When using code, you must indicate the script type in the code block. The user cannot provide any other feedback or perform any other action beyond executing the code you suggest. The user can't modify your code. So do not suggest incomplete code which requires users to modify. Don't use a code block if it's not intended to be executed by the user.
If you want the user to save the code in a file before executing it, put # filename: <filename> inside the code block as the first line. Don't include multiple code blocks in one response. Do not ask users to copy and paste the result. Instead, use 'print' function for the output when relevant. Check the execution result returned by the user.
If the result indicates there is an error, fix the error and output the code again. Suggest the full code instead of partial code or code changes. If the error can't be fixed or if the task is not solved even after the code is executed successfully, analyze the problem, revisit your assumption, collect additional info you need, and think of a different approach to try.
When you find an answer, verify the answer carefully. Include verifiable evidence in your response if possible.
Reply "TERMINATE" in the end when everything is done."""
            )
        ]
        # A dictionary to store the messages for each task session.
        self._session_memory: Dict[str, List[LLMMessage]] = {}

    @message_handler
    async def handle_task(self, message: TaskMessage, cancellation_token: CancellationToken) -> None:
        # Create a new session.
        session_id = str(uuid.uuid4())
        self._session_memory.setdefault(session_id, []).append(UserMessage(content=message.content, source="user"))

        # Make an inference to the model.
        response = await self._model_client.create(self._system_messages + self._session_memory[session_id])
        assert isinstance(response.content, str)
        self._session_memory[session_id].append(
            AssistantMessage(content=response.content, source=self.metadata["name"])
        )

        # Publish the code execution task.
        self.publish_message(
            CodeExecutionTask(content=response.content, session_id=session_id), cancellation_token=cancellation_token
        )

    @message_handler
    async def handle_code_execution_result(
        self, message: CodeExecutionTaskResult, cancellation_token: CancellationToken
    ) -> None:
        # Store the code execution output.
        self._session_memory[message.session_id].append(UserMessage(content=message.output, source="user"))

        # Make an inference to the model -- reflection on the code execution output happens here.
        response = await self._model_client.create(self._system_messages + self._session_memory[message.session_id])
        assert isinstance(response.content, str)
        self._session_memory[message.session_id].append(
            AssistantMessage(content=response.content, source=self.metadata["name"])
        )

        if "TERMINATE" in response.content:
            # If the task is completed, publish a message with the completion content.
            self.publish_message(TaskCompletion(content=response.content), cancellation_token=cancellation_token)
            return

        # Publish the code execution task.
        self.publish_message(
            CodeExecutionTask(content=response.content, session_id=message.session_id),
            cancellation_token=cancellation_token,
        )


class Executor(TypeRoutedAgent):
    """An agent that executes code."""

    def __init__(self, executor: CodeExecutor) -> None:
        super().__init__(description="A code executor agent.")
        self._executor = executor

    @message_handler
    async def handle_code_execution(self, message: CodeExecutionTask, cancellation_token: CancellationToken) -> None:
        # Extract the code block from the message.
        code_blocks = self._extract_code_blocks(message.content)
        if not code_blocks:
            # If no code block is found, publish a message with an error.
            self.publish_message(
                CodeExecutionTaskResult(
                    output="Error: no Markdown code block found.", exit_code=1, session_id=message.session_id
                ),
                cancellation_token=cancellation_token,
            )
            return
        # Execute code blocks.
        future = asyncio.get_event_loop().run_in_executor(None, self._executor.execute_code_blocks, code_blocks)
        cancellation_token.link_future(future)
        result = await future
        # Publish the code execution result.
        self.publish_message(
            CodeExecutionTaskResult(output=result.output, exit_code=result.exit_code, session_id=message.session_id),
            cancellation_token=cancellation_token,
        )

    def _extract_code_blocks(self, markdown_text: str) -> List[CodeBlock]:
        pattern = re.compile(r"```(?:\s*([\w\+\-]+))?\n([\s\S]*?)```")
        matches = pattern.findall(markdown_text)
        code_blocks: List[CodeBlock] = []
        for match in matches:
            language = match[0].strip() if match[0] else ""
            code_content = match[1]
            code_blocks.append(CodeBlock(code=code_content, language=language))
        return code_blocks


class TerminationHandler(DefaultInterventionHandler):
    """A handler that listens for termination messages."""

    def __init__(self) -> None:
        self._terminated = False

    async def on_publish(self, message: Any, *, sender: AgentId | None) -> Any:
        if isinstance(message, TaskCompletion):
            self._terminated = True
            print("--------------------")
            print("Task completed:")
            print(message.content)
        return message

    @property
    def terminated(self) -> bool:
        return self._terminated


async def main(task: str, temp_dir: str) -> None:
    # Create the termination handler.
    termination_handler = TerminationHandler()

    # Create the runtime with the termination handler.
    runtime = SingleThreadedAgentRuntime(intervention_handler=termination_handler)

    # Register the agents.
    runtime.register("coder", lambda: Coder(model_client=OpenAIChatCompletionClient(model="gpt-4-turbo")))
    runtime.register("executor", lambda: Executor(executor=LocalCommandLineCodeExecutor(work_dir=temp_dir)))

    # Publish the task message.
    runtime.publish_message(TaskMessage(content=task), namespace="default")

    # Run the runtime until the termination condition is met.
    while not termination_handler.terminated:
        await runtime.process_next()


if __name__ == "__main__":
    import logging
    from datetime import datetime

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("agnext").setLevel(logging.DEBUG)

    task = f"Today is {datetime.today()}, create a plot of NVDA and TSLA stock prices YTD using yfinance."

    asyncio.run(main(task, "."))
