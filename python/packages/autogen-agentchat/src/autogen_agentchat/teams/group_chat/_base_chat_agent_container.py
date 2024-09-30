import asyncio
import sys
from typing import List

from autogen_core.base import AgentId, AgentType, MessageContext
from autogen_core.components import DefaultTopicId, event
from autogen_core.components.models import FunctionExecutionResult
from autogen_core.components.tool_agent import ToolException

from ...agents import BaseChatAgent, MultiModalMessage, StopMessage, TextMessage, ToolCallMessage, ToolCallResultMessage
from ._events import ContentPublishEvent, ContentRequestEvent
from ._sequential_routed_agent import SequentialRoutedAgent


class BaseChatAgentContainer(SequentialRoutedAgent):
    """A core agent class that delegates message handling to an
    :class:`autogen_agentchat.agents.BaseChatAgent` so that it can be used in a
    group chat team.

    Args:
        parent_topic_type (str): The topic type of the parent orchestrator.
        agent (BaseChatAgent): The agent to delegate message handling to.
        tool_agent_type (AgentType): The agent type of the tool agent to use for tool calls.
    """

    def __init__(self, parent_topic_type: str, agent: BaseChatAgent, tool_agent_type: AgentType) -> None:
        super().__init__(description=agent.description)
        self._parent_topic_type = parent_topic_type
        self._agent = agent
        self._message_buffer: List[TextMessage | MultiModalMessage | StopMessage] = []
        self._tool_agent_id = AgentId(type=tool_agent_type, key=self.id.key)

    @event
    async def handle_content_publish(self, message: ContentPublishEvent, ctx: MessageContext) -> None:
        """Handle a content publish event by appending the content to the buffer."""
        if not isinstance(message.agent_message, TextMessage | MultiModalMessage | StopMessage):
            raise ValueError(
                f"Unexpected message type: {type(message.agent_message)}. "
                "The message must be a text, multimodal, or stop message."
            )
        self._message_buffer.append(message.agent_message)

    @event
    async def handle_content_request(self, message: ContentRequestEvent, ctx: MessageContext) -> None:
        """Handle a content request event by passing the messages in the buffer
        to the delegate agent and publish the response."""
        response = await self._agent.on_messages(self._message_buffer, ctx.cancellation_token)

        # Handle tool calls.
        while isinstance(response, ToolCallMessage):
            # TODO: use logging instead of print
            sys.stdout.write(f"{'-'*80}\n{self._agent.name}:\n{response.content}\n")
            # Execute functions called by the model by sending messages to tool agent.
            results: List[FunctionExecutionResult | BaseException] = await asyncio.gather(
                *[
                    self.send_message(
                        message=call,
                        recipient=self._tool_agent_id,
                        cancellation_token=ctx.cancellation_token,
                    )
                    for call in response.content
                ]
            )
            # Combine the results in to a single response and handle exceptions.
            function_results: List[FunctionExecutionResult] = []
            for result in results:
                if isinstance(result, FunctionExecutionResult):
                    function_results.append(result)
                elif isinstance(result, ToolException):
                    function_results.append(FunctionExecutionResult(content=f"Error: {result}", call_id=result.call_id))
                elif isinstance(result, BaseException):
                    raise result  # Unexpected exception.
            # Create a new tool call result message.
            feedback = ToolCallResultMessage(content=function_results, source=self._tool_agent_id.type)
            # TODO: use logging instead of print
            sys.stdout.write(f"{'-'*80}\n{self._tool_agent_id.type}:\n{feedback.content}\n")
            # Forward the feedback to the agent.
            response = await self._agent.on_messages([feedback], ctx.cancellation_token)

        # Publish the response.
        assert isinstance(response, TextMessage | MultiModalMessage | StopMessage)
        self._message_buffer.clear()
        await self.publish_message(
            ContentPublishEvent(agent_message=response), topic_id=DefaultTopicId(type=self._parent_topic_type)
        )
