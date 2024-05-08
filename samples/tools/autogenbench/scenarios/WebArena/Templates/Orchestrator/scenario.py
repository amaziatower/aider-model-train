import os
import json
import testbed_utils
import autogen
import evaluation_harness
import re
import copy
from autogen.agentchat.contrib.orchestrator import Orchestrator
from autogen.agentchat.contrib.multimodal_web_surfer import MultimodalWebSurferAgent
from autogen.agentchat.contrib.mmagent import MultimodalAgent
from autogen.runtime_logging import logging_enabled, log_event
from autogen.code_utils import content_str

from evaluation_harness.env_config import (
    ACCOUNTS,
    GITLAB,
    MAP,
    REDDIT,
    SHOPPING,
    SHOPPING_ADMIN,
    WIKIPEDIA,
    HOMEPAGE,
    LOGIN_PROMPTS,
    SITE_DESCRIPTIONS,
    url_to_sitename,
)

testbed_utils.init()
##############################

REPLACEMENTS = {
    "__REDDIT__": REDDIT,
    "__SHOPPING__": SHOPPING,
    "__SHOPPING_ADMIN__": SHOPPING_ADMIN,
    "__GITLAB__": GITLAB,
    "__WIKIPEDIA__": WIKIPEDIA,
    "__MAP__": MAP,
    "__HOMEPAGE__": HOMEPAGE,
}

# Expand the prompt and the full task
task_prompt = ""
TASK = None
with open("task_prompt.json.txt", "rt") as fh:
    task_prompt = fh.read()
with open("task_prompt.json", "wt") as fh:
    for k in REPLACEMENTS:
        task_prompt = task_prompt.replace(k, REPLACEMENTS[k])
    fh.write(task_prompt)
    TASK = json.loads(task_prompt)

full_task = ""
with open("full_task.json.txt", "rt") as fh:
    full_task = fh.read()
with open("full_task.json", "wt") as fh:
    for k in REPLACEMENTS:
        full_task = full_task.replace(k, REPLACEMENTS[k])
    fh.write(full_task)

# Load the LLM config list
config_list = autogen.config_list_from_json("OAI_CONFIG_LIST")
llm_config = testbed_utils.default_llm_config(config_list, timeout=300)

if logging_enabled():
    log_event(os.path.basename(__file__), name="loaded_config_lists")

login_assistant = MultimodalAgent(
    "login_assistant",
    system_message="""You are a general-purpose AI assistant and can handle many questions -- but you don't have access to a web browser. However, the user you are talking to does have a browser, and you can see the screen. Provide short direct instructions to them to take you where you need to go to answer the initial question posed to you.

Once the user has taken the final necessary action to complete the task, and you have fully addressed the initial request, reply with the word TERMINATE.""",
    description="A helpful and general-purpose AI assistant that has strong language skills, Python skills, and Linux command line skills.",
    is_termination_msg=lambda x: str(x).find("TERMINATE") >= 0 or str(x).find("FINAL ANSWER") >= 0,
    code_execution_config=False,
    llm_config=llm_config,
)

assistant = MultimodalAgent(
    "assistant",
    system_message=autogen.AssistantAgent.DEFAULT_SYSTEM_MESSAGE,
    description=autogen.AssistantAgent.DEFAULT_DESCRIPTION,
    is_termination_msg=lambda x: str(x).find("TERMINATE") >= 0 or str(x).find("FINAL ANSWER") >= 0,
    code_execution_config=False,
    llm_config=llm_config,
)

user_proxy_name = "computer_terminal"
user_proxy = autogen.UserProxyAgent(
    user_proxy_name,
    human_input_mode="NEVER",
    description="A computer terminal that performs no other action than running Python scripts (provided to it quoted in ```python code blocks), or sh shell scripts (provided to it quoted in ```sh code blocks)",
    is_termination_msg=lambda x: str(x).find("TERMINATE") >= 0 or str(x).find("FINAL ANSWER") >= 0,
    code_execution_config={
        "work_dir": "coding",
        "use_docker": False,
    },
    default_auto_reply=f'Invalid {user_proxy_name} input: no code block detected.\nPlease provide {user_proxy_name} a complete Python script or a shell (sh) script to run. Scripts should appear in code blocks beginning "```python" or "```sh" respectively.',
    max_consecutive_auto_reply=15,
)

web_surfer = MultimodalWebSurferAgent(
    "web_surfer",
    llm_config=llm_config,
    is_termination_msg=lambda x: str(x).find("TERMINATE") >= 0 or str(x).find("FINAL ANSWER") >= 0,
    human_input_mode="NEVER",
    headless=True,
    browser_channel="chromium",
    browser_data_dir=None,
    start_page=HOMEPAGE,
    debug_dir=os.getenv("WEB_SURFER_DEBUG_DIR", None),
)

maestro = Orchestrator(
    "orchestrator",
    agents=[assistant, user_proxy, web_surfer],
    llm_config=llm_config,
    response_format_is_supported=False,
)

# Login to the necessary websites
for site in TASK["sites"]:
    if site in ["reddit", "gitlab", "shopping", "shopping_admin"]:
        if logging_enabled():
            log_event(os.path.basename(__file__), name="start_" + site + "_task")
        try:
            login_assistant.initiate_chat(
                web_surfer,
                message=LOGIN_PROMPTS[site],
                clear_history=True,
            )
        except Exception as e:
            import traceback

            if logging_enabled():
                exc_type = type(e).__name__
                exc_message = str(e)
                exc_traceback = traceback.format_exc().splitlines()
                log_event(
                    os.path.basename(__file__),
                    name="exception_thrown",
                    exc_type=exc_type,
                    exc_message=exc_message,
                    exc_traceback=exc_traceback,
                )

            raise e
        login_assistant.reset()
        web_surfer.reset()


# Navigate to the starting url
if logging_enabled():
    log_event(os.path.basename(__file__), name="navigate_start_url")
start_url = TASK["start_url"]
if start_url == REDDIT:
    start_url = start_url + "/forums"
user_proxy.send(f"Type '{start_url}' into the address bar.", web_surfer, request_reply=True)

login_assistant.reset()
web_surfer.reset()  # NOTE: This resets the message history, but not the browser state. We rely on this.. but it's notat all a very obvious behavior.

print("MAIN TASK STARTING !#!#")

# Provide some background about the pages
site_description_prompt = ""
sitename = url_to_sitename(start_url)
if sitename:
    site_description_prompt = ", " + SITE_DESCRIPTIONS[sitename]

if logging_enabled():
    log_event(os.path.basename(__file__), name="main_task_initiate_chat")

try:
    web_surfer.initiate_chat(
        maestro,
        message=f"""
We are visiting the website {start_url}{site_description_prompt}. On this website, please complete the following task:

{TASK['intent']}
""".strip(),
        clear_history=True,
    )
except Exception as e:
    import traceback

    if logging_enabled():
        exc_type = type(e).__name__
        exc_message = str(e)
        exc_traceback = traceback.format_exc().splitlines()
        log_event(
            os.path.basename(__file__),
            name="exception_thrown",
            exc_type=exc_type,
            exc_message=exc_message,
            exc_traceback=exc_traceback,
        )

    raise e


# Extract a final answer
#########################
def _has_image(message):
    if isinstance(message["content"], list):
        for elm in message["content"]:
            if elm.get("type", "") == "image_url":
                return True
    return False


def _create_with_images(client, messages, max_images=1, **kwargs):
    # Clone the messages to give context, but remove old screenshots
    history = []
    n_images = 0
    for m in messages[::-1]:
        # Create a shallow copy
        message = {}
        message.update(m)

        # If there's an image, then consider replacing it with a string
        if _has_image(message):
            n_images += 1
            if n_images > max_images:
                message["content"] = content_str(message["content"])

        # Prepend the message -- since we are iterating backwards
        history.insert(0, message)
    return client.create(messages=history, **kwargs)


def response_preparer(inner_messages):
    client = autogen.OpenAIWrapper(**llm_config)
    messages = [
        {
            "role": "user",
            "content": f"""Earlier you were asked the following:

{TASK['intent']}

Your team then worked diligently to address that request. Here is a transcript of that conversation:""",
        }
    ]

    # copy them to this context
    for message in inner_messages:
        if not message.get("content"):
            continue
        message = copy.deepcopy(message)
        message["role"] = "user"
        messages.append(message)

    # ask for the final answer
    messages.append(
        {
            "role": "user",
            "content": f"""Read the above conversation and output a FINAL ANSWER to the original request. The original request is repeated here for convenience:

{TASK['intent']}

To output the final answer, use the following template: FINAL ANSWER: [YOUR FINAL ANSWER]
Your FINAL ANSWER should be as few words as possible.
If the original request was not a question, or you did not find a definitive answer, simply summarize the final state of the page or task as your FINAL ANSWER.""",
        }
    )

    response = _create_with_images(client, messages, context=None)
    if "finish_reason='content_filter'" in str(response):
        raise Exception(str(response))
    extracted_response = client.extract_text_or_completion_object(response)[0]
    return extracted_response


if logging_enabled():
    log_event(os.path.basename(__file__), name="extract_final_answer")
final_answer = response_preparer(maestro.orchestrated_messages)

m = re.search("FINAL ANSWER:(.*)$", final_answer, re.DOTALL)
if m:
    final_answer = m.group(1).strip()

if logging_enabled():
    log_event(os.path.basename(__file__), name="final_answer", final_answer=final_answer)

print('page.stop("' + final_answer + '")')
print("MAIN TASK COMPLETE !#!#")

########## EVALUATION ##########

# playwright = web_surfer._playwright
context = web_surfer._context
page = web_surfer._page
cdp_session = context.new_cdp_session(page)
config_file = "full_task.json"

import nltk

nltk.download("punkt")

evaluator = evaluation_harness.evaluator_router(config_file)
score = evaluator(
    trajectory=evaluation_harness.make_answer_trajecotry(final_answer),
    config_file=config_file,
    page=page,
    client=cdp_session,
    azure_config=llm_config
)

if logging_enabled():
    log_event(os.path.basename(__file__), name="final_score", final_score=str(score))
print("FINAL SCORE: " + str(score))

################################
testbed_utils.finalize(agents=[web_surfer, user_proxy, assistant, login_assistant, maestro])
