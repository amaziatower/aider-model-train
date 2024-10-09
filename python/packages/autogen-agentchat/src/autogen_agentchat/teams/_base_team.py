from dataclasses import dataclass
from typing import List, Protocol

from ..agents import ChatMessage
from ._termination import TerminationCondition


@dataclass
class TeamRunResult:
    messages: List[ChatMessage]
    """The messages generated by the team."""


class BaseTeam(Protocol):
    async def run(self, task: str, *, termination_condition: TerminationCondition | None = None) -> TeamRunResult:
        """Run the team on a given task until the termination condition is met."""
        ...
