# ruff: noqa: E722
import re
import time
import os
import json
import io
import base64
import pathlib
from PIL import Image
from urllib.parse import urlparse, quote, quote_plus, unquote, urlunparse, parse_qs
from typing import Any, Dict, List, Optional, Union, Callable, Literal, Tuple
from typing_extensions import Annotated
from playwright.sync_api import sync_playwright
from playwright._impl._errors import TimeoutError
from .... import Agent, ConversableAgent, OpenAIWrapper
from ....code_utils import content_str
from .state_of_mark import add_state_of_mark

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x


# Sentinels for constructor
DEFAULT_CHANNEL = object()

# Viewport dimensions
VIEWPORT_HEIGHT = 900
VIEWPORT_WIDTH = 1440

# Size of the image we send to the MLM
# Current values represent a 0.85 scaling to fit within the GPT-4v short-edge constraints (768px)
MLM_HEIGHT = 765
MLM_WIDTH = 1224

# State-of-mark IDs for static browser controls
MARK_ID_ADDRESS_BAR = 0
MARK_ID_BACK = 1
MARK_ID_RELOAD = 2
MARK_ID_SEARCH_BAR = 3
MARK_ID_PAGE_UP = 4
MARK_ID_PAGE_DOWN = 5


class MultimodalWebSurferAgent(ConversableAgent):
    """(In preview) A multimodal agent that acts as a web surfer that can search the web and visit web pages."""

    DEFAULT_DESCRIPTION = "A helpful assistant with access to a web browser. Ask them to perform web searches, open pages, and interact with content (e.g., clicking links, scrolling the viewport, etc., filling in form fields, etc.)"

    def __init__(
        self,
        name: str,
        system_message: Optional[Union[str, List[str]]] = None,
        description: Optional[str] = DEFAULT_DESCRIPTION,
        is_termination_msg: Optional[Callable[[Dict[str, Any]], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "TERMINATE",
        function_map: Optional[Dict[str, Callable]] = None,
        code_execution_config: Union[Dict, Literal[False]] = False,
        llm_config: Optional[Union[Dict, Literal[False]]] = None,
        mlm_config: Optional[Union[Dict, Literal[False]]] = None,
        default_auto_reply: Optional[Union[str, Dict, None]] = "",
        headless=True,
        chromium_channel=DEFAULT_CHANNEL,
        chromium_data_dir=None,
        start_page="https://www.bing.com/",
        debug_dir=os.getcwd(),
    ):
        super().__init__(
            name=name,
            system_message=system_message,
            description=description,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            function_map=function_map,
            code_execution_config=code_execution_config,
            llm_config=llm_config,
            default_auto_reply=default_auto_reply,
        )
        # self._mlm_config = mlm_config
        # self._mlm_client = OpenAIWrapper(**self._mlm_config)
        self.start_page = start_page
        self.debug_dir = debug_dir

        # Create the playwright instance
        launch_args = {"headless": headless}
        if chromium_channel is not DEFAULT_CHANNEL:
            launch_args["channel"] = chromium_channel
        self._playwright = sync_playwright().start()

        # Create the context -- are we launching a persistent instance?
        if chromium_data_dir is None:
            browser = self._playwright.chromium.launch(**launch_args)
            self._context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
            )
        else:
            self._context = self._playwright.chromium.launch_persistent_context(chromium_data_dir, **launch_args)

        # Create the page
        self._page = self._context.new_page()
        self._page.set_viewport_size({"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
        self._page.add_init_script(path=os.path.join(os.path.abspath(os.path.dirname(__file__)), "page_script.js"))
        self._page.goto(self.start_page)
        self._page.wait_for_load_state()
        time.sleep(1)

        # Prepare the debug directory -- which stores the screenshots generated throughout the process
        if self.debug_dir:
            if not os.path.isdir(self.debug_dir):
                os.mkdir(self.debug_dir)
            debug_html = os.path.join(self.debug_dir, "screenshot.html")
            with open(debug_html, "wt") as fh:
                fh.write(
                    f"""
<html style="width:100%; margin: 0px; padding: 0px;">
<body style="width: 100%; margin: 0px; padding: 0px;">
    <img src="screenshot.png" id="main_image" style="width: 100%; max-width: {VIEWPORT_WIDTH}px; margin: 0px; padding: 0px;">
    <script language="JavaScript">
var counter = 0;
setInterval(function() {{
   counter += 1;
   document.getElementById("main_image").src = "screenshot.png?bc=" + counter;
}}, 300);
    </script>
</body>
</html>
""".strip()
                )
            self._page.screenshot(path=os.path.join(self.debug_dir, "screenshot.png"))
            print(f"Multimodal Web Surfer debug screens: {pathlib.Path(os.path.abspath(debug_html)).as_uri()}\n")

        self._reply_func_list = []
        self.register_reply([Agent, None], MultimodalWebSurferAgent.generate_surfer_reply)
        self.register_reply([Agent, None], ConversableAgent.generate_code_execution_reply)
        self.register_reply([Agent, None], ConversableAgent.generate_function_call_reply)
        self.register_reply([Agent, None], ConversableAgent.check_termination_and_human_reply)

    def generate_surfer_reply(
        self,
        messages: Optional[List[Dict[str, str]]] = None,
        sender: Optional[Agent] = None,
        config: Optional[OpenAIWrapper] = None,
    ) -> Tuple[bool, Optional[Union[str, Dict[str, str]]]]:
        """Generate a reply using autogen.oai."""
        if messages is None:
            messages = self._oai_messages[sender]

        # Clone the messages to give context, removing old screenshots
        history = []
        for m in messages:
            message = {}
            message.update(m)
            message["content"] = content_str(message["content"])
            history.append(message)

        # Ask the page for interactive elements, then prepare the state-of-mark screenshot
        rects = self._get_interactive_rects()
        viewport = self._get_visual_viewport()
        som_screenshot, visible_rects = add_state_of_mark(self._page.screenshot(), rects)

        if self.debug_dir:
            som_screenshot.save(os.path.join(self.debug_dir, "screenshot.png"))

        # Focus hint
        focused = self._get_focused_rect_id()
        focused_hint = ""
        if focused:
            name = rects.get(focused, {}).get("aria-name", "")
            if name:
                name = f"(and name '{name}') "
            focused_hint = (
                "\nThe "
                + rects.get(focused, {}).get("role", "control")
                + " with ID "
                + focused
                + " "
                + name
                + "currently has the input focus.\n"
            )

        # Include all the static elements
        text_labels = f"""
  {{ "id": {MARK_ID_BACK}, "aria-role": "button", "html_tag": "button", "actions": ["click"], "name": "browser back button" }},
  {{ "id": {MARK_ID_ADDRESS_BAR}, "aria-role": "textbox",   "html_tag": "input, type=text", "actions": ["type"],  "name": "browser address input" }},
  {{ "id": {MARK_ID_SEARCH_BAR}, "aria-role": "searchbox", "html_tag": "input, type=text", "actions": ["type"],  "name": "browser web search input" }},"""

        # We can scroll up
        if viewport["pageTop"] > 5:
            text_labels += f"""
  {{ "id": {MARK_ID_PAGE_UP}, "aria-role": "scrollbar", "html_tag": "button", "actions": ["click", "scroll_up"], "name": "browser scroll up control" }},"""

        # Can scroll down
        if (viewport["pageTop"] + viewport["height"] + 5) < viewport["scrollHeight"]:
            text_labels += f"""
  {{ "id": {MARK_ID_PAGE_DOWN}, "aria-role": "scrollbar", "html_tag": "button", "actions": ["click", "scroll_down"], "name": "browser scroll down control" }},"""

        # Everything visible
        for r in visible_rects:
            if r in rects:
                actions = ["'click'"]
                if rects[r]["role"] in ["textbox", "searchbox", "search"]:
                    actions = ["'type'"]
                if rects[r]["v-scrollable"]:
                    actions.append("'scroll_up'")
                    actions.append("'scroll_down'")
                actions = "[" + ",".join(actions) + "]"

                text_labels += f"""
   {{ "id": {r}, "aria-role": "{rects[r]['role']}", "html_tag": "{rects[r]['tag_name']}", "actions": "{actions}", "name": "{rects[r]['aria-name']}" }},"""

        text_prompt = f"""
Consider the following screenshot of a web browser, which is open to the page '{self._page.url}'. In this screenshot, interactive elements are outlined in bounding boxes of different colors. Each bounding box has a numeric ID label in the same color. Additional information about each visible label is listed below:

[
{text_labels}
]
{focused_hint}
You are to respond to the user's most recent request by selecting a browser action to perform. Please output the appropriate action in the following format:

TARGET:   <id of interactive element>
ACTION:   <One single action from the element's list of actions>
ARGUMENT: <The action' argument, if any. For example, the text to type if the action is typing>
""".strip()

        # Scale the screenshot for the MLM, and close the original
        scaled_screenshot = som_screenshot.resize((MLM_WIDTH, MLM_HEIGHT))
        som_screenshot.close()
        if self.debug_dir:
            scaled_screenshot.save(os.path.join(self.debug_dir, "screenshot_scaled.png"))

        # Add the multimodal message and make the request
        history.append(self._make_mm_message(text_prompt, scaled_screenshot))
        som_screenshot.close()  # Don't do this if messages start accepting PIL images
        response = self.client.create(messages=history)
        text_response = "\n" + self.client.extract_text_or_completion_object(response)[0].strip() + "\n"

        target = None
        target_name = None
        m = re.search(r"\nTARGET:\s*(.*?)\n", text_response)
        if m:
            target = m.group(1).strip()

            # Non-critical. Mainly for pretty logs
            target_name = rects.get(target, {}).get("aria-name")
            if target_name:
                target_name = target_name.strip()

        action = None
        m = re.search(r"\nACTION:\s*(.*?)\n", text_response)
        if m:
            action = m.group(1).strip().lower()

        m = re.search(r"\nARGUMENT:\s*(.*?)\n", text_response)
        if m:
            argument = m.group(1).strip()

        try:
            if target == str(MARK_ID_ADDRESS_BAR) and argument:
                self._log_to_console("goto", arg=argument)
                # Check if the argument starts with a known protocol
                if argument.startswith(("https://", "http://", "file://")):
                    self._visit_page(argument)
                # If the argument contains a space, treat it as a search query
                elif " " in argument:
                    self._visit_page(f"https://www.bing.com/search?q={quote_plus(argument)}&FORM=QBLH")
                # Otherwise, prefix with https://
                else:
                    argument = "https://" + argument
                    self._visit_page(argument)
            elif target == str(MARK_ID_SEARCH_BAR) and argument:
                self._log_to_console("search", arg=argument)
                self._visit_page(f"https://www.bing.com/search?q={quote_plus(argument)}&FORM=QBLH")
            elif target == str(MARK_ID_PAGE_UP):
                self._log_to_console("page_up")
                self._page_up()
            elif target == str(MARK_ID_PAGE_DOWN):
                self._log_to_console("page_down")
                self._page_down()
            elif action == "click":
                self._log_to_console("click", target=target_name if target_name else target)
                self._click_id(target)
            elif action == "type":
                self._log_to_console("type", target=target_name if target_name else target, arg=argument)
                self._fill_id(target, argument if argument else "")
            elif action == "scroll_up":
                self._log_to_console("scroll_up", target=target_name if target_name else target)
                self._scroll_id(target, "up")
            elif action == "scroll_down":
                self._log_to_console("scroll_down", target=target_name if target_name else target)
                self._scroll_id(target, "down")
            else:
                # No action
                return True, text_response
        except ValueError as e:
            return True, str(e)

        self._page.wait_for_load_state()
        time.sleep(1)

        # Descrive the viewport of the new page in words
        viewport = self._get_visual_viewport()
        percent_visible = int(viewport["height"] * 100 / viewport["scrollHeight"])
        percent_scrolled = int(viewport["pageTop"] * 100 / viewport["scrollHeight"])
        if percent_scrolled < 1:  # Allow some rounding error
            position_text = "at the top of the page"
        elif percent_scrolled + percent_visible >= 99:  # Allow some rounding error
            position_text = "at the bottom of the page"
        else:
            position_text = str(percent_scrolled) + "% down from the top of the page"

        new_screenshot = self._page.screenshot()
        if self.debug_dir:
            with open(os.path.join(self.debug_dir, "screenshot.png"), "wb") as png:
                png.write(new_screenshot)

        # Return the complete observation
        return True, self._make_mm_message(
            f"Here is a screenshot of [{self._page.title()}]({self._page.url}). The viewport shows {percent_visible}% of the webpage, and is positioned {position_text}.",
            new_screenshot,
        )

    def _image_to_data_uri(self, image):
        """
        Image can be a bytes string, a Binary file-like stream, or PIL Image.
        """
        image_bytes = image
        if isinstance(image, Image.Image):
            image_buffer = io.BytesIO()
            image.save(image_buffer, format="PNG")
            image_bytes = image_buffer.getvalue()
        elif isinstance(image, io.BytesIO):
            image_bytes = image_buffer.getvalue()
        elif isinstance(image, io.BufferedIOBase):
            image_bytes = image.read()

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/png;base64,{image_base64}"

    def _make_mm_message(self, text_content, image_content):
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text_content},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._image_to_data_uri(image_content),
                    },
                },
            ],
        }

    def _get_interactive_rects(self):
        try:
            with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "page_script.js"), "rt") as fh:
                self._page.evaluate(fh.read())
        except:
            pass
        return self._page.evaluate("MultimodalWebSurfer.getInteractiveRects();")

    def _get_visual_viewport(self):
        try:
            with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "page_script.js"), "rt") as fh:
                self._page.evaluate(fh.read())
        except:
            pass
        return self._page.evaluate("MultimodalWebSurfer.getVisualViewport();")

    def _get_focused_rect_id(self):
        try:
            with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "page_script.js"), "rt") as fh:
                self._page.evaluate(fh.read())
        except:
            pass
        return self._page.evaluate("MultimodalWebSurfer.getFocusedElementId();")

    def _on_new_page(self, page):
        self._page = page
        self._page.set_viewport_size({"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
        time.sleep(0.2)
        self._page.add_init_script(path=os.path.join(os.path.abspath(os.path.dirname(__file__)), "page_script.js"))
        self._page.wait_for_load_state()

        title = None
        try:
            title = self._page.title()
        except:
            pass

        self._log_to_console("new_tab", arg=title if title else self._page.url)

    def _visit_page(self, url):
        self._page.goto(url)

    def _page_down(self):
        self._page.evaluate(f"window.scrollBy(0, {VIEWPORT_HEIGHT-50});")

    def _page_up(self):
        self._page.evaluate(f"window.scrollBy(0, -{VIEWPORT_HEIGHT-50});")

    def _click_id(self, identifier):
        target = self._page.locator(f"[__elementId='{identifier}']")

        # See if it exists
        try:
            target.wait_for(timeout=100)
        except TimeoutError:
            raise ValueError("No such element.")

        # Click it
        box = target.bounding_box()
        try:
            # Git it a chance to open a new page
            with self._page.expect_event("popup", timeout=1000) as page_info:
                self._page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            self._on_new_page(page_info.value)
        except TimeoutError:
            pass

    def _fill_id(self, identifier, value):
        target = self._page.locator(f"[__elementId='{identifier}']")

        # See if it exists
        try:
            target.wait_for(timeout=100)
        except TimeoutError:
            raise ValueError("No such element.")

        # Fill it
        target.focus()
        target.fill(value)
        self._page.keyboard.press("Enter")

    def _scroll_id(self, identifier, direction):
        self._page.evaluate(
            f"""
        (function() {{
            let elm = document.querySelector("[__elementId='{identifier}']");
            if (elm) {{
                if ("{direction}" == "up") {{
                    elm.scrollTop = Math.max(0, elm.scrollTop - elm.clientHeight);
                }}
                else {{
                    elm.scrollTop = Math.min(elm.scrollHeight - elm.clientHeight, elm.scrollTop + elm.clientHeight);
                }}
            }}
        }})();
    """
        )

    def _log_to_console(self, action, target="", arg=""):
        if len(target) > 50:
            target = target[0:47] + "..."
        if len(arg) > 50:
            arg = arg[0:47] + "..."
        log_str = action + "("
        if target:
            log_str += '"' + re.sub(r"\s+", " ", target).strip() + '",'
        if arg:
            log_str += '"' + re.sub(r"\s+", " ", arg).strip() + '"'
        log_str = log_str.rstrip(",") + ")"
        print(
            colored("\n>>>>>>>> BROWSER ACTION " + log_str, "cyan"),
            flush=True,
        )
