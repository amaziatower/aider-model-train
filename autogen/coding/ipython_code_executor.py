import base64
import json
import os
import re
import uuid
from queue import Empty
from typing import Any, List

from jupyter_client import KernelManager  # type: ignore[attr-defined]
from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel
from pydantic import BaseModel, Field

from ..agentchat.agent import LLMAgent
from ..code_utils import DEFAULT_TIMEOUT
from .base import CodeBlock, CodeExtractor, CodeResult
from .markdown_code_extractor import MarkdownCodeExtractor

__all__ = ("IPythonCodeExecutor",)


class IPythonCodeExecutor(BaseModel):
    """A code executor class that executes code statefully using IPython kernel.

    Each execution is stateful and can access variables created from previous
    executions in the same session.
    """

    class UserCapability:
        """An AgentCapability class that gives agent ability use a stateful
        code executor."""

        DEFAULT_SYSTEM_MESSAGE_UPDATE = """# IPython Coding Capability
You have been given coding capability to solve tasks using Python code in a stateful IPython kernel.
You are responsible for writing the code, and the user is responsible for executing the code.

When you write Python code, put the code in a markdown code block with the language set to Python.
For example:
```python
x = 3
```
You can use the variable `x` in subsequent code blocks.
```python
print(x)
```

Write code incrementally and leverage the statefulness of the kernel to avoid repeating code.
Import libraries in a separate code block.
Define a function or a class in a separate code block.
Run code that produces output in a separate code block.
Run code that involves expensive operations like download, upload, and call external APIs in a separate code block.

When your code produces an output, the output will be returned to you.
Because you have limited conversation memory, if your code creates an image,
the output will be a path to the image instead of the image itself.
"""

        def add_to_agent(self, agent: LLMAgent) -> None:
            """Add this capability to an agent."""
            # system message is a string or a list of strings
            system_message = agent.system_message + self.DEFAULT_SYSTEM_MESSAGE_UPDATE
            agent.update_system_message(system_message)

    timeout: int = Field(default=DEFAULT_TIMEOUT, ge=1, description="The timeout for code execution.")
    kernel: str = Field(default="python3", description="The kernel to use.")
    output_dir: str = Field(default=".", description="The directory to save output files.")

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        # Check if the kernel is installed.
        if self.kernel not in KernelSpecManager().find_kernel_specs():
            raise ValueError(
                f"Kernel {self.kernel} is not installed. "
                "Please first install it with "
                f"`python -m ipykernel install --user --name {self.kernel}`."
            )
        self._kernel_manager = KernelManager()
        self._kernel_manager.start_kernel()
        self._kernel_client = self._kernel_manager.client()
        self._kernel_client.start_channels()
        self._timeout = self.timeout

    @property
    def user_capability(self) -> "IPythonCodeExecutor.UserCapability":
        """Export a user capability that can be added to an agent."""
        return IPythonCodeExecutor.UserCapability()

    @property
    def code_extractor(self) -> CodeExtractor:
        """Export a code extractor that can be used by an agent."""
        return MarkdownCodeExtractor()

    def execute_code_blocks(self, code_blocks: List[CodeBlock]) -> CodeResult:
        self._kernel_client.wait_for_ready()
        outputs = []
        for code_block in code_blocks:
            code = self._process_code(code_block.code)
            self._kernel_client.execute(code, store_history=True)
            while True:
                try:
                    msg = self._kernel_client.get_iopub_msg(timeout=self._timeout)
                    msg_type = msg["msg_type"]
                    content = msg["content"]
                    if msg_type in ["execute_result", "display_data"]:
                        for data_type, data in content["data"].items():
                            if data_type == "text/plain":
                                # Output is a text.
                                outputs.append(data)
                            elif data_type.startswith("image/"):
                                # Output is an image.
                                path = self._save_image(data)
                                outputs.append(f"Image data saved to {path}")
                            elif data_type == "text/html":
                                # Output is an html.
                                path = self._save_html(data)
                                outputs.append(f"HTML data saved to {path}")
                            else:
                                # Output raw data.
                                outputs.append(json.dumps(data))
                    elif msg_type == "stream":
                        # Output is a text.
                        outputs.append(content["text"])
                    elif msg_type == "error":
                        # Output is an error.
                        return CodeResult(
                            exit_code=1,
                            output=f"ERROR: {content['ename']}: {content['evalue']}\n{content['traceback']}",
                        )
                    if msg_type == "status" and content["execution_state"] == "idle":
                        break
                # handle time outs.
                except Empty:
                    return CodeResult(
                        exit_code=1,
                        output=f"ERROR: Timeout waiting for output from code block: {code_block.code}",
                    )
        # We return the full output.
        return CodeResult(exit_code=0, output="\n".join([str(output) for output in outputs]))

    def restart(self) -> None:
        """Restart a new session."""
        self._kernel_client.stop_channels()
        self._kernel_manager.shutdown_kernel()
        self._kernel_manager = KernelManager(kernel_name=self.kernel)
        self._kernel_manager.start_kernel()
        self._kernel_client = self._kernel_manager.client()
        self._kernel_client.start_channels()

    def _save_image(self, image_data_base64: str) -> str:
        """Save image data to a file."""
        image_data = base64.b64decode(image_data_base64)
        # Randomly generate a filename.
        filename = f"{uuid.uuid4().hex}.png"
        path = os.path.join(self.output_dir, filename)
        with open(path, "wb") as f:
            f.write(image_data)
        return os.path.abspath(path)

    def _save_html(self, html_data: str) -> str:
        """Save html data to a file."""
        # Randomly generate a filename.
        filename = f"{uuid.uuid4().hex}.html"
        path = os.path.join(self.output_dir, filename)
        with open(path, "w") as f:
            f.write(html_data)
        return os.path.abspath(path)

    def _process_code(self, code: str) -> str:
        """Process code before execution."""
        # Find lines that start with `! pip install` and make sure "-qqq" flag is added.
        lines = code.split("\n")
        for i, line in enumerate(lines):
            # use regex to find lines that start with `! pip install` or `!pip install`.
            match = re.search(r"^! ?pip install", line)
            if match is not None:
                if "-qqq" not in line:
                    lines[i] = line.replace(match.group(0), match.group(0) + " -qqq")
        return "\n".join(lines)
