import asyncio
import logging
import json
import os
import re
import nltk

from typing import Any, Dict, List, Tuple, Union
from agnext.application import SingleThreadedAgentRuntime
from agnext.application.logging import EVENT_LOGGER_NAME
from agnext.components.models import (
    AzureOpenAIChatCompletionClient,
    ChatCompletionClient,
    ModelCapabilities,
    UserMessage,
    SystemMessage,
    LLMMessage,
)
from agnext.components.code_executor import LocalCommandLineCodeExecutor
from agnext.application.logging import EVENT_LOGGER_NAME
from team_one.markdown_browser import MarkdownConverter, UnsupportedFormatException
from team_one.agents.coder import Coder, Executor
from team_one.agents.orchestrator import RoundRobinOrchestrator, LedgerOrchestrator
from team_one.messages import BroadcastMessage, OrchestrationEvent, RequestReplyMessage, ResetMessage, DeactivateMessage
from team_one.agents.multimodal_web_surfer import MultimodalWebSurfer
from team_one.agents.file_surfer import FileSurfer
from team_one.utils import LogHandler, message_content_to_str, create_completion_client_from_env


import evaluation_harness
from evaluation_harness.env_config import (
    ACCOUNTS,
    GITLAB,
    MAP,
    REDDIT,
    SHOPPING,
    SHOPPING_ADMIN,
    WIKIPEDIA,
    HOMEPAGE,
    SITE_URLS,
    LOGIN_PROMPTS,
    SITE_DESCRIPTIONS,
    url_to_sitename,
)

REPLACEMENTS = {
    "__REDDIT__": REDDIT,
    "__SHOPPING__": SHOPPING,
    "__SHOPPING_ADMIN__": SHOPPING_ADMIN,
    "__GITLAB__": GITLAB,
    "__WIKIPEDIA__": WIKIPEDIA,
    "__MAP__": MAP,
    "__HOMEPAGE__": HOMEPAGE,
}

nltk.download("punkt")


async def response_preparer(task: str, source: str, client: ChatCompletionClient, transcript: List[LLMMessage]) -> str:
    messages: List[LLMMessage] = [
        UserMessage(
            content=f"Earlier you were asked the following:\n\n{task}\n\nYour team then worked diligently to address that request. Here is a transcript of that conversation:",
            source=source,
        )
    ]

    # copy them to this context
    for message in transcript:
        messages.append(
            UserMessage(
                content = message_content_to_str(message.content),
                # TODO fix this -> remove type ignore
                source=message.source, # type: ignore
            )
        )

    # ask for the final answer
    messages.append(
        UserMessage(
            content= f"""
Read the above conversation and output a FINAL ANSWER to the original request. The original request is repeated here for convenience:

{task}

To output the final answer, use the following template: FINAL ANSWER: [YOUR FINAL ANSWER]
Your FINAL ANSWER should be as few words as possible.
If the original request was not a question, or you did not find a definitive answer, simply summarize the final state of the page or task as your FINAL ANSWER.""",
            source=source,
        )
    )

    response = await client.create(messages)
    assert isinstance(response.content, str)
    return response.content


async def main() -> None:
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
        if TASK["start_url"] == REDDIT: 
            TASK["start_url"] = TASK["start_url"] + "/forums/all"

    full_task = ""
    with open("full_task.json.txt", "rt") as fh:
        full_task = fh.read()
    with open("full_task.json", "wt") as fh:
        for k in REPLACEMENTS:
            full_task = full_task.replace(k, REPLACEMENTS[k])
        fh.write(full_task)

    # Create the runtime.
    runtime = SingleThreadedAgentRuntime()

    # Create the AzureOpenAI client, with AAD auth
    # token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    client = AzureOpenAIChatCompletionClient(
        api_version="2024-02-15-preview",
        azure_endpoint="https://aif-complex-tasks-west-us-3.openai.azure.com/",
        model="gpt-4o-2024-05-13",
        model_capabilities=ModelCapabilities(
            function_calling=True, json_output=True, vision=True
        ),
        # azure_ad_token_provider=token_provider
    )

    # Login assistant
    login_assistant = await runtime.register_and_get_proxy(
        "LoginAssistant",
        lambda: Coder(
            model_client=client,
            system_messages=[
                SystemMessage("""You are a general-purpose AI assistant and can handle many questions -- but you don't have access to a web browser. However, the user you are talking to does have a browser, and you can see the screen. Provide short direct instructions to them to take you where you need to go to answer the initial question posed to you.

Once the user has taken the final necessary action to complete the task, and you have fully addressed the initial request, reply with the word TERMINATE.""",
                )
            ],
        ),
    )

    # Web surfer
    web_surfer = await runtime.register_and_get_proxy(
        "WebSurfer",
        lambda: MultimodalWebSurfer(), # Configuration is set later by init()
    )

    actual_surfer = await runtime.try_get_underlying_agent_instance(web_surfer.id, type=MultimodalWebSurfer)
    await actual_surfer.init(model_client=client, downloads_folder=os.getcwd(), browser_channel="chromium")

    # Round-robin orchestrator
    round_robin_orc = await runtime.register_and_get_proxy("round_robin_orc", lambda: RoundRobinOrchestrator(
        agents=[web_surfer, login_assistant],
        )
    )

    # Login to the necessary websites
    for site in TASK["sites"]:
        if site in ["reddit", "gitlab", "shopping", "shopping_admin"]:
            actual_surfer.start_page = SITE_URLS[site]

            run_context = runtime.start()
            await runtime.publish_message(ResetMessage(), namespace="default")
            await runtime.publish_message(
                BroadcastMessage(content=UserMessage(content=LOGIN_PROMPTS[site], source="human")),
                namespace="default",
            )
            await run_context.stop_when_idle()

    # Deactivate the login-related agents
    run_context = runtime.start()
    await runtime.send_message(DeactivateMessage(), login_assistant.id)
    await runtime.send_message(DeactivateMessage(), round_robin_orc.id)
    await run_context.stop_when_idle()

    # By this point, we should be logged in. Prepare for the main event
    coder = await runtime.register_and_get_proxy(
        "Coder",
        lambda: Coder(model_client=client),
    )

    executor = await runtime.register_and_get_proxy(
        "Executor",
        lambda: Executor(
            "A agent for executing code", executor=LocalCommandLineCodeExecutor()
        ),
    )
    
    file_surfer = await runtime.register_and_get_proxy(
        "file_surfer",
        lambda: FileSurfer(model_client=client),
    )
   
    orchestrator = await runtime.register_and_get_proxy("orchestrator", lambda: LedgerOrchestrator(
        agents=[coder, executor, file_surfer, web_surfer],
        model_client=client,
    ))

    # The main event
    actual_surfer.start_page = TASK["start_url"]
    run_context = runtime.start()
    await runtime.send_message(ResetMessage(), web_surfer.id)

    # Provide some background about the pages
    site_description_prompt = ""
    sitename = url_to_sitename(TASK["start_url"])
    if sitename:
        site_description_prompt = ", " + SITE_DESCRIPTIONS[sitename]
    task = f"Your web browser is currently open to the website {TASK['start_url']}{site_description_prompt}. On this website, please complete the following task:\n\n{TASK['intent']}"

    await runtime.publish_message(
        BroadcastMessage(content=UserMessage(content=task.strip(), source="human")),
        namespace="default",
    )

    await run_context.stop_when_idle()

    # Output the final answer
    actual_orchestrator = await runtime.try_get_underlying_agent_instance(orchestrator.id, type=LedgerOrchestrator)
    transcript: List[LLMMessage] = actual_orchestrator._chat_history # type: ignore
    final_answer = await response_preparer(task=TASK["intent"], source=(await orchestrator.metadata)["name"], client=client, transcript=transcript)

    m = re.search("FINAL ANSWER:(.*)$", final_answer, re.DOTALL)
    if m:
        final_answer = m.group(1).strip()

    print('page.stop("' + final_answer + '")')
    print("MAIN TASK COMPLETE !#!#")

    ########## EVALUATION ##########
    context = actual_surfer._context
    page = actual_surfer._page
    cdp_session = context.new_cdp_session(page)
    config_file = "full_task.json"
    
    evaluator = evaluation_harness.evaluator_router(config_file)
    score = "N/A"
    #score = evaluator(
    #    trajectory=evaluation_harness.make_answer_trajecotry(final_answer),
    #    config_file=config_file,
    #    page=page,
    #    client=cdp_session,
    #    azure_config=llm_config,
    #)
    
    print("FINAL SCORE: " + str(score))


if __name__ == "__main__":
    logger = logging.getLogger(EVENT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    log_handler = LogHandler()
    logger.handlers = [log_handler]
    asyncio.run(main())
