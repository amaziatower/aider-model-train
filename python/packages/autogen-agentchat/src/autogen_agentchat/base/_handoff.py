import logging
from typing import Any, Dict

from autogen_core.tools import FunctionTool, Tool
from pydantic import BaseModel, Field, model_validator

from .. import EVENT_LOGGER_NAME

event_logger = logging.getLogger(EVENT_LOGGER_NAME)


class Handoff(BaseModel):
    """Handoff configuration."""

    target: str
    """The name of the target agent to handoff to."""

    description: str = Field(default=None)
    """The description of the handoff such as the condition under which it should happen and the target agent's ability.
    If not provided, it is generated from the target agent's name."""

    name: str = Field(default=None)
    """The name of this handoff configuration. If not provided, it is generated from the target agent's name."""

    message: str = Field(default=None)
    """The message to the target agent.
    If not provided, it is generated from the target agent's name."""

    @model_validator(mode="before")
    @classmethod
    def set_defaults(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("description") is None:
            values["description"] = f"Handoff to {values['target']}."
        if values.get("name") is None:
            values["name"] = f"transfer_to_{values['target']}".lower()
        else:
            name = values["name"]
            if not isinstance(name, str):
                raise ValueError(f"Handoff name must be a string: {values['name']}")
            # Check if name is a valid identifier.
            if not name.isidentifier():
                raise ValueError(f"Handoff name must be a valid identifier: {values['name']}")
        if values.get("message") is None:
            values["message"] = (
                f"Transferred to {values['target']}, adopting the role of {values['target']} immediately."
            )
        return values

    @property
    def handoff_tool(self) -> Tool:
        """Create a handoff tool from this handoff configuration."""

        def _handoff_tool() -> str:
            return self.message

        return FunctionTool(_handoff_tool, name=self.name, description=self.description)
