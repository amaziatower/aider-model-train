import json
from dataclasses import dataclass
from typing import List

from .. import FunctionCall, MessageContext, RoutedAgent
from .._routed_agent import rpc
from ..models import FunctionExecutionResult
from ..tools import Tool

__all__ = [
    "ToolAgent",
    "ToolException",
    "ToolNotFoundException",
    "InvalidToolArgumentsException",
    "ToolExecutionException",
]


@dataclass
class ToolException:
    call_id: str
    content: str


@dataclass
class ToolNotFoundException(ToolException):
    pass


@dataclass
class InvalidToolArgumentsException(ToolException):
    pass


@dataclass
class ToolExecutionException(ToolException):
    pass


class ToolAgent(RoutedAgent):
    """A tool agent accepts direct messages of the type `FunctionCall`,
    executes the requested tool with the provided arguments, and returns the
    result as `FunctionExecutionResult` messages.

    Args:
        description (str): The description of the agent.
        tools (List[Tool]): The list of tools that the agent can execute.
    """

    def __init__(
        self,
        description: str,
        tools: List[Tool],
    ) -> None:
        super().__init__(description)
        self._tools = tools

    @property
    def tools(self) -> List[Tool]:
        return self._tools

    @rpc
    async def handle_function_call(
        self, message: FunctionCall, ctx: MessageContext
    ) -> FunctionExecutionResult | ToolNotFoundException | InvalidToolArgumentsException | ToolExecutionException:
        """Handles a `FunctionCall` message by executing the requested tool with the provided arguments.

        Args:
            message (FunctionCall): The function call message.
            cancellation_token (CancellationToken): The cancellation token.

        Returns:
            FunctionExecutionResult: The result of the function execution.

        Raises:
            ToolNotFoundException: If the tool is not found.
            InvalidToolArgumentsException: If the tool arguments are invalid.
            ToolExecutionException: If the tool execution fails.
        """
        tool = next((tool for tool in self._tools if tool.name == message.name), None)
        if tool is None:
            return ToolNotFoundException(call_id=message.id, content=f"Error: Tool not found: {message.name}")
        else:
            try:
                arguments = json.loads(message.arguments)
                result = await tool.run_json(args=arguments, cancellation_token=ctx.cancellation_token)
                result_as_str = tool.return_value_as_string(result)
            except json.JSONDecodeError:
                return InvalidToolArgumentsException(
                    call_id=message.id, content=f"Error: Invalid arguments: {message.arguments}"
                )
            except Exception as e:
                return ToolExecutionException(call_id=message.id, content=f"Error: {e}")
        return FunctionExecutionResult(content=result_as_str, call_id=message.id)
