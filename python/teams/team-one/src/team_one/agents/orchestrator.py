import json
from typing import Any, Dict, List, Optional

from agnext.components.models import AssistantMessage, ChatCompletionClient, LLMMessage, SystemMessage, UserMessage
from agnext.core import AgentProxy, MessageContext, TopicId

from ..messages import BroadcastMessage, OrchestrationEvent, ResetMessage
from .base_orchestrator import BaseOrchestrator, logger
from .orchestrator_prompts import (
    ORCHESTRATOR_CLOSED_BOOK_PROMPT,
    ORCHESTRATOR_LEDGER_PROMPT,
    ORCHESTRATOR_PLAN_PROMPT,
    ORCHESTRATOR_SYNTHESIZE_PROMPT,
    ORCHESTRATOR_SYSTEM_MESSAGE,
    ORCHESTRATOR_UPDATE_FACTS_PROMPT,
    ORCHESTRATOR_UPDATE_PLAN_PROMPT,
)


class RoundRobinOrchestrator(BaseOrchestrator):
    def __init__(
        self,
        agents: List[AgentProxy],
        description: str = "Round robin orchestrator",
        max_rounds: int = 20,
    ) -> None:
        super().__init__(agents=agents, description=description, max_rounds=max_rounds)

    async def _select_next_agent(self, message: LLMMessage) -> AgentProxy:
        self._current_index = (self._num_rounds) % len(self._agents)
        return self._agents[self._current_index]


class LedgerOrchestrator(BaseOrchestrator):
    DEFAULT_SYSTEM_MESSAGES = [
        SystemMessage(ORCHESTRATOR_SYSTEM_MESSAGE),
    ]

    def __init__(
        self,
        agents: List[AgentProxy],
        model_client: ChatCompletionClient,
        description: str = "Ledger-based orchestrator",
        system_messages: List[SystemMessage] = DEFAULT_SYSTEM_MESSAGES,
        closed_book_prompt: str = ORCHESTRATOR_CLOSED_BOOK_PROMPT,
        plan_prompt: str = ORCHESTRATOR_PLAN_PROMPT,
        synthesize_prompt: str = ORCHESTRATOR_SYNTHESIZE_PROMPT,
        ledger_prompt: str = ORCHESTRATOR_LEDGER_PROMPT,
        update_facts_prompt: str = ORCHESTRATOR_UPDATE_FACTS_PROMPT,
        update_plan_prompt: str = ORCHESTRATOR_UPDATE_PLAN_PROMPT,
        max_rounds: int = 20,
        max_time: float = float("inf"),
        max_stalls_before_replan: int = 3,
        max_replans: int = 3,
    ) -> None:
        super().__init__(agents=agents, description=description, max_rounds=max_rounds, max_time=max_time)

        self._model_client = model_client

        # prompt-based parameters
        self._system_messages = system_messages
        self._closed_book_prompt = closed_book_prompt
        self._plan_prompt = plan_prompt
        self._synthesize_prompt = synthesize_prompt
        self._ledger_prompt = ledger_prompt
        self._update_facts_prompt = update_facts_prompt
        self._update_plan_prompt = update_plan_prompt

        self._chat_history: List[LLMMessage] = []
        self._should_replan = True
        self._max_stalls_before_replan = max_stalls_before_replan
        self._stall_counter = 0
        self._max_replans = max_replans
        self._replan_counter = 0

        self._team_description = ""
        self._task = ""
        self._facts = ""
        self._plan = ""

    def _get_closed_book_prompt(self, task: str) -> str:
        return self._closed_book_prompt.format(task=task)

    def _get_plan_prompt(self, team: str) -> str:
        return self._plan_prompt.format(team=team)

    def _get_synthesize_prompt(self, task: str, team: str, facts: str, plan: str) -> str:
        return self._synthesize_prompt.format(task=task, team=team, facts=facts, plan=plan)

    def _get_ledger_prompt(self, task: str, team: str, names: List[str]) -> str:
        return self._ledger_prompt.format(task=task, team=team, names=names)

    def _get_update_facts_prompt(self, task: str, facts: str) -> str:
        return self._update_facts_prompt.format(task=task, facts=facts)

    def _get_update_plan_prompt(self, team: str) -> str:
        return self._update_plan_prompt.format(team=team)

    async def _get_team_description(self) -> str:
        team_description = ""
        for agent in self._agents:
            metadata = await agent.metadata
            name = metadata["type"]
            description = metadata["description"]
            team_description += f"{name}: {description}\n"
        return team_description

    async def _get_team_names(self) -> List[str]:
        return [(await agent.metadata)["type"] for agent in self._agents]

    def _get_message_str(self, message: LLMMessage) -> str:
        if isinstance(message.content, str):
            return message.content
        else:
            result = ""
            for content in message.content:
                if isinstance(content, str):
                    result += content + "\n"
            assert len(result) > 0
        return result

    async def _initialize_task(self, task: str) -> None:
        self._task = task
        self._team_description = await self._get_team_description()

        # Shallow-copy the conversation
        planning_conversation = [m for m in self._chat_history]

        # 1. GATHER FACTS
        # create a closed book task and generate a response and update the chat history
        planning_conversation.append(
            UserMessage(content=self._get_closed_book_prompt(self._task), source=self.metadata["type"])
        )
        response = await self._model_client.create(self._system_messages + planning_conversation)

        assert isinstance(response.content, str)
        self._facts = response.content
        planning_conversation.append(AssistantMessage(content=self._facts, source=self.metadata["type"]))

        # 2. CREATE A PLAN
        ## plan based on available information
        planning_conversation.append(
            UserMessage(content=self._get_plan_prompt(self._team_description), source=self.metadata["type"])
        )
        response = await self._model_client.create(self._system_messages + planning_conversation)

        assert isinstance(response.content, str)
        self._plan = response.content

        # At this point, the planning conversation is dropped.

    async def _update_facts_and_plan(self) -> None:
        # Shallow-copy the conversation
        planning_conversation = [m for m in self._chat_history]

        # Update the facts
        planning_conversation.append(
            UserMessage(content=self._get_update_facts_prompt(self._task, self._facts), source=self.metadata["type"])
        )
        response = await self._model_client.create(self._system_messages + planning_conversation)

        assert isinstance(response.content, str)
        self._facts = response.content
        planning_conversation.append(AssistantMessage(content=self._facts, source=self.metadata["type"]))

        # Update the plan
        planning_conversation.append(
            UserMessage(content=self._get_update_plan_prompt(self._team_description), source=self.metadata["type"])
        )
        response = await self._model_client.create(self._system_messages + planning_conversation)

        assert isinstance(response.content, str)
        self._plan = response.content

        # At this point, the planning conversation is dropped.

    async def update_ledger(self) -> Dict[str, Any]:
        max_json_retries = 10

        team_description = await self._get_team_description()
        names = await self._get_team_names()
        ledger_prompt = self._get_ledger_prompt(self._task, team_description, names)

        ledger_user_messages: List[LLMMessage] = [UserMessage(content=ledger_prompt, source=self.metadata["type"])]

        assert max_json_retries > 0
        for _ in range(max_json_retries):
            ledger_response = await self._model_client.create(
                self._system_messages + self._chat_history + ledger_user_messages,
                json_output=True,
            )
            ledger_str = ledger_response.content

            try:
                assert isinstance(ledger_str, str)
                ledger_dict: Dict[str, Any] = json.loads(ledger_str)
                required_keys = [
                    "is_request_satisfied",
                    "is_in_loop",
                    "is_progress_being_made",
                    "next_speaker",
                    "instruction_or_question",
                ]
                key_error = False
                for key in required_keys:
                    if key not in ledger_dict:
                        ledger_user_messages.append(AssistantMessage(content=ledger_str, source="self"))
                        ledger_user_messages.append(
                            UserMessage(content=f"KeyError: '{key}'", source=self.metadata["type"])
                        )
                        key_error = True
                        break
                    if "answer" not in ledger_dict[key]:
                        ledger_user_messages.append(AssistantMessage(content=ledger_str, source="self"))
                        ledger_user_messages.append(
                            UserMessage(content=f"KeyError: '{key}.answer'", source=self.metadata["type"])
                        )
                        key_error = True
                        break
                if key_error:
                    continue
                return ledger_dict
            except json.JSONDecodeError as e:
                logger.info(
                    OrchestrationEvent(
                        f"{self.metadata['type']} (error)",
                        f"Failed to parse ledger information: {ledger_str}",
                    )
                )
                raise e

        raise ValueError("Failed to parse ledger information after multiple retries.")

    async def _handle_broadcast(self, message: BroadcastMessage, ctx: MessageContext) -> None:
        self._chat_history.append(message.content)
        await super()._handle_broadcast(message, ctx)

    async def _select_next_agent(self, message: LLMMessage) -> Optional[AgentProxy]:
        # Check if the task is still unset, in which case this message contains the task string
        if len(self._task) == 0:
            await self._initialize_task(self._get_message_str(message))

            # At this point the task, plan and facts shouls all be set
            assert len(self._task) > 0
            assert len(self._facts) > 0
            assert len(self._plan) > 0
            assert len(self._team_description) > 0

            # Send everyone the plan
            synthesized_prompt = self._get_synthesize_prompt(
                self._task, self._team_description, self._facts, self._plan
            )
            topic_id = TopicId("default", self.id.key)
            await self.publish_message(
                BroadcastMessage(content=UserMessage(content=synthesized_prompt, source=self.metadata["type"])),
                topic_id=topic_id,
            )

            logger.info(
                OrchestrationEvent(
                    f"{self.metadata['type']} (thought)",
                    f"Initial plan:\n{synthesized_prompt}",
                )
            )

            self._replan_counter = 0
            self._stall_counter = 0

            synthesized_message = AssistantMessage(content=synthesized_prompt, source=self.metadata["type"])
            self._chat_history.append(synthesized_message)

            # Answer from this synthesized message
            return await self._select_next_agent(synthesized_message)

        # Orchestrate the next step
        ledger_dict = await self.update_ledger()
        logger.info(
            OrchestrationEvent(
                f"{self.metadata['type']} (thought)",
                f"Updated Ledger:\n{json.dumps(ledger_dict, indent=2)}",
            )
        )

        # Task is complete
        if ledger_dict["is_request_satisfied"]["answer"] is True:
            logger.info(
                OrchestrationEvent(
                    f"{self.metadata['type']} (thought)",
                    "Request satisfied.",
                )
            )
            return None

        # Stalled or stuck in a loop
        stalled = ledger_dict["is_in_loop"]["answer"] or not ledger_dict["is_progress_being_made"]["answer"]
        if stalled:
            self._stall_counter += 1

            # We exceeded our stall counter, so we need to replan, or exit
            if self._stall_counter > self._max_stalls_before_replan:
                self._replan_counter += 1
                self._stall_counter = 0

                # We exceeded our replan counter
                if self._replan_counter > self._max_replans:
                    logger.info(
                        OrchestrationEvent(
                            f"{self.metadata['type']} (thought)",
                            "Replan counter exceeded... Terminating.",
                        )
                    )
                    return None
                # Let's create a new plan
                else:
                    logger.info(
                        OrchestrationEvent(
                            f"{self.metadata['type']} (thought)",
                            "Stalled.... Replanning...",
                        )
                    )

                    # Update our plan.
                    await self._update_facts_and_plan()

                    # Reset everyone, then rebroadcast the new plan
                    self._chat_history = [self._chat_history[0]]
                    topic_id = TopicId("default", self.id.key)
                    await self.publish_message(ResetMessage(), topic_id=topic_id)

                    # Send everyone the NEW plan
                    synthesized_prompt = self._get_synthesize_prompt(
                        self._task, self._team_description, self._facts, self._plan
                    )
                    topic_id = TopicId("default", self.id.key)
                    await self.publish_message(
                        BroadcastMessage(content=UserMessage(content=synthesized_prompt, source=self.metadata["type"])),
                        topic_id=topic_id,
                    )

                    logger.info(
                        OrchestrationEvent(
                            f"{self.metadata['type']} (thought)",
                            f"New plan:\n{synthesized_prompt}",
                        )
                    )

                    synthesized_message = AssistantMessage(content=synthesized_prompt, source=self.metadata["type"])
                    self._chat_history.append(synthesized_message)

                    # Answer from this synthesized message
                    return await self._select_next_agent(synthesized_message)

        # If we goit this far, we were not starting, done, or stuck
        next_agent_name = ledger_dict["next_speaker"]["answer"]
        for agent in self._agents:
            if (await agent.metadata)["type"] == next_agent_name:
                # broadcast a new message
                instruction = ledger_dict["instruction_or_question"]["answer"]
                user_message = UserMessage(content=instruction, source=self.metadata["type"])
                assistant_message = AssistantMessage(content=instruction, source=self.metadata["type"])
                logger.info(OrchestrationEvent(f"{self.metadata['type']} (-> {next_agent_name})", instruction))
                self._chat_history.append(assistant_message)  # My copy
                topic_id = TopicId("default", self.id.key)
                await self.publish_message(
                    BroadcastMessage(content=user_message, request_halt=False),
                    topic_id=topic_id,
                )  # Send to everyone else
                return agent

        return None
