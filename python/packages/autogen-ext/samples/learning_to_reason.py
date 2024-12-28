import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, ChainedTokenCredential, AzureCliCredential, get_bearer_token_provider
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_ext.agents.web_surfer._utils import message_content_to_str
from autogen_agentchat.ui._console import Console
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    LLMMessage,
    SystemMessage,
    UserMessage,
)
from typing import (
    Tuple,
)
from autogen_ext.agentic_memory import AgenticMemory, PageLog, Grader


MEMORY_DIR = "~/agentic_memory_archive"
PAGELOG_DIR = "~/pagelogs/"
RUN_SUBDIR = "run_21_cl_base"

# Default client parameters
TEMPERATURE = 0.8
MAX_TOKENS = 4096
PRESENCE_PENALTY = 0.0
FREQUENCY_PENALTY = 0.0
TOP_P = 1.0
MAX_RETRIES = 65535


def define_tasks_with_answers():
    tasks_with_answers = []

    # Task index 0
    tasks_with_answers.append({
        "task": """You ask 100 people: 'How many of you are liars?' They all answer: 'At least one of us is not a liar.' But you know that at least one of the 100 is a liar. How many of them are liars?""",
        "expected_answer": "100"})

    # Task index 1
    tasks_with_answers.append({
        "task": """You are Van Helsing, a renowned vampire hunter. A Count of Moldova, La\u021bcu IV, son of  Costea, has tasked you with investigating the village of \u0218irnea in neighboring Wallachia. The Count's advisors have reported that a vampire was spotted crossing the border near the village, and would like you to investigate it.

You travel to the village of \u0218irnea, and you begin your investigation. One night, just before dawn, you catch a glimpse of a man in a long black cape with red lining leaping from roof-top to roof-top with superhuman agility. It's a vampire! You try to chase the creature back to its home, but the creature is too fast. However, because of the remoteness of the village, you know with absolute certainty that the vampire must be a resident of the village. You decide that your best course of action will be to visit all 100 residents of the town during the day. You know something about vampires and humans that will make your investigation possible; humans always tell the truth, but vampires always lie.

In the afternoon, you go from house to house, speaking with all 100 residents of \u0218irnea. You ask everyone the same question: \"How many vampires are living in \u0218irnea\". Everyone in the village gives the same response, \"At least one of us is a human.\"\n\nHow many residents of \u0218irnea have been turned into vampires?""",
        "expected_answer": "100"})

    # Task index 2
    tasks_with_answers.append({
        "task": """Three guards stand at a door. You need to determine how many of them are truthful, and you already know that one of them is not. You ask each one 'How many guards here tell the truth?' Each one says 'One or more of us always tells the truth'. How many of the guards tell the truth?""",
        "expected_answer": "3"})

    return tasks_with_answers


def create_client(page_log=None):
    # Choose one.
    # return create_oai_client(page_log)
    # return create_aoai_client(page_log)
    return create_trapi_client(page_log)


def create_oai_client(page_log):
    # Create an OpenAI client
    model_name = "gpt-4o-2024-08-06"
    client = OpenAIChatCompletionClient(
        model=model_name,
        api_key="",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        presence_penalty=PRESENCE_PENALTY,
        frequency_penalty=FREQUENCY_PENALTY,
        top_p=TOP_P,
        max_retries=MAX_RETRIES,
    )
    if page_log is not None:
        page_log.append_entry_line("Client:  {}".format(client._resolved_model))
        page_log.append_entry_line("  created through OpenAI directly")
    page_log.append_entry_line("  temperature:  {}".format(TEMPERATURE))
    return client


def create_aoai_client(page_log):
    # Create an Azure OpenAI client
    token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    azure_deployment = "gpt-4o-2024-08-06-eval"
    model = "gpt-4o-2024-08-06"
    azure_endpoint = "https://agentic2.openai.azure.com/"
    client = AzureOpenAIChatCompletionClient(
        azure_endpoint=azure_endpoint,
        azure_ad_token_provider=token_provider,
        azure_deployment=azure_deployment,
        api_version="2024-06-01",
        model=model,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        presence_penalty=PRESENCE_PENALTY,
        frequency_penalty=FREQUENCY_PENALTY,
        top_p=TOP_P,
        max_retries=MAX_RETRIES,
    )
    if page_log is not None:
        page_log.append_entry_line("Client:  {}".format(client._resolved_model))
        page_log.append_entry_line("  created through Azure OpenAI")
    page_log.append_entry_line("  temperature:  {}".format(TEMPERATURE))
    return client


def create_trapi_client(page_log):
    # Create an Azure OpenAI client through TRAPI
    token_provider = get_bearer_token_provider(ChainedTokenCredential(
        AzureCliCredential(),
        DefaultAzureCredential(
            exclude_cli_credential=True,
            # Exclude other credentials we are not interested in.
            exclude_environment_credential=True,
            exclude_shared_token_cache_credential=True,
            exclude_developer_cli_credential=True,
            exclude_powershell_credential=True,
            exclude_interactive_browser_credential=True,
            exclude_visual_studio_code_credentials=True,
            # managed_identity_client_id=os.environ.get("DEFAULT_IDENTITY_CLIENT_ID"),  # See the TRAPI docs
        )
    ), "api://trapi/.default")
    model = "gpt-4o-2024-08-06"  # This is (for instance) the OpenAI model name, which is used to look up capabilities.
    azure_deployment = 'gpt-4o_2024-08-06'  # This is DeploymentName in the table at https://aka.ms/trapi/models
    trapi_suffix = 'msraif/shared'  # This is TRAPISuffix (without /openai) in the table at https://aka.ms/trapi/models
    endpoint = f'https://trapi.research.microsoft.com/{trapi_suffix}'
    api_version = '2024-10-21'  # From https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation#latest-ga-api-release
    client = AzureOpenAIChatCompletionClient(
        azure_ad_token_provider=token_provider,
        model=model,
        azure_deployment=azure_deployment,
        azure_endpoint=endpoint,
        api_version=api_version,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        presence_penalty=PRESENCE_PENALTY,
        frequency_penalty=FREQUENCY_PENALTY,
        top_p=TOP_P,
        max_retries=MAX_RETRIES,
    )
    if page_log is not None:
        page_log.append_entry_line("Client:  {}".format(client._resolved_model))
        page_log.append_entry_line("  created through TRAPI")
    page_log.append_entry_line("  temperature:  {}".format(TEMPERATURE))
    return client


async def assign_task_to_magentic_one(task, model_client, page_log) -> Tuple[str, str]:
    page = page_log.begin_page(
        summary="assign_task_to_magentic_one",
        details='',
        method_call="assign_task_to_magentic_one")

    page.add_lines(task)

    general_agent = AssistantAgent(
        "general_agent",
        model_client,
        description="A general GPT-4o AI assistant capable of performing a variety of tasks.", )

    web_surfer = MultimodalWebSurfer(
        name="web_surfer",
        model_client=model_client,
        downloads_folder="logs",
        debug_dir="logs",
        to_save_screenshots=True,
    )

    team = MagenticOneGroupChat(
        [general_agent, web_surfer],
        model_client=model_client,
        max_turns=20,
    )

    # Get the team's text response to the task.
    stream = team.run_stream(task=task)
    task_result = await Console(stream)
    response_str = "\n".join([message_content_to_str(message.content) for message in task_result.messages])
    page.add_lines("-----  RESPONSE  -----\n\n{}\n".format(response_str), flush=True)

    # MagenticOne's response is the chat history, which we use here as the work history.
    work_history = response_str

    page_log.finish_page(page)
    return response_str, work_history


async def assign_task_to_client(task, client, page_log):
    page = page_log.begin_page(
        summary="assign_task_to_client",
        details='',
        method_call="assign_task_to_client")

    page.add_lines(task)

    system_message = SystemMessage(content="""You are a helpful and thoughtful assistant.
In responding to every user message, you follow the same multi-step process given here:
1. Explain your understanding of the user message in detail, covering all the important points.
2. List as many possible responses as you can think of.
3. Carefully list and weigh the pros and cons (if any) of each possible response.
4. Critique the pros and cons above, looking for any flaws in your reasoning. But don't make up flaws that don't exist.
5. Decide on the best response, looping back to step 1 if none of the responses are satisfactory.
6. Finish by providing your final response in the particular format requested by the user.""")
    user_message = UserMessage(content=task, source="User")

    input_messages = [system_message] + [user_message]
    response = await client.create(input_messages)
    response_str = response.content

    # Log the model call
    page_log.add_model_call(description="Ask the model",
                            details="to complete the task", input_messages=input_messages,
                            response=response,
                            num_input_tokens=0, caller='assign_task_to_client')
    page.add_lines("-----  RESPONSE  -----\n\n{}\n".format(response_str), flush=True)

    # Use the response as the work history as well.
    work_history = response_str

    page_log.finish_page(page)
    return response_str, work_history


async def train(task_with_answer, max_train_trials, max_test_trials, task_assignment_callback, reset_memory,
                client, page_log) -> None:
    page = page_log.begin_page(
        summary="train",
        details='',
        method_call="train")
    memory = AgenticMemory(reset=reset_memory, client=client, page_log=page_log,
                           memory_dir=MEMORY_DIR, run_subdir=RUN_SUBDIR)
    await memory.train_on_task(
        task=task_with_answer["task"],
        expected_answer=task_with_answer["expected_answer"],
        task_assignment_callback=task_assignment_callback,
        final_format_instructions="",
        max_train_trials=max_train_trials,
        max_test_trials=max_test_trials)
    page_log.finish_page(page)


async def test(task_with_answer, num_trials, task_assignment_callback, use_memory, reset_memory,
               client, page_log) -> Tuple[str, int, int]:
    page = page_log.begin_page(
        summary="test",
        details='',
        method_call="test")

    grader = Grader(client, page_log)

    if use_memory:
        page.add_lines("Testing with memory.\n", flush=True)
        memory = AgenticMemory(reset=reset_memory, client=client, page_log=page_log,
                               memory_dir=MEMORY_DIR, run_subdir=RUN_SUBDIR)
        response, num_successes, num_trials = await memory.test_on_task(
            task=task_with_answer["task"],
            expected_answer=task_with_answer["expected_answer"],
            task_assignment_callback=task_assignment_callback,
            num_trials=num_trials)
    else:
        page.add_lines("Testing without memory.\n", flush=True)
        response = None
        num_successes = 0
        for trial in range(num_trials):
            page.add_lines("\n-----  TRIAL {}  -----\n".format(trial + 1), flush=True)
            page.add_lines("Try to solve the task.\n", flush=True)
            response, _ = await task_assignment_callback(task_with_answer["task"], client, page_log)

            response_is_correct, extracted_answer = await grader.response_is_correct(
                task_with_answer["task"], response, task_with_answer["expected_answer"])
            page.add_lines("Extracted answer:  {}".format(extracted_answer), flush=True)
            if response_is_correct:
                page.add_lines("Answer is CORRECT.\n", flush=True)
                num_successes += 1
            else:
                page.add_lines("Answer is INCORRECT.\n", flush=True)

    page.add_lines("\nSuccess rate:  {}%\n".format(round((num_successes / num_trials) * 100)), flush=True)

    page_log.finish_page(page)
    return response, num_successes, num_trials


async def train_and_test(task_index, max_train_trials, max_test_trials, task_assignment_callback, client, page_log):
    page = page_log.begin_page(
        summary="train_and_test",
        details='',
        method_call="train_and_test")

    tasklist = define_tasks_with_answers()
    task_with_answer = tasklist[task_index]

    num_loops = 10  # Normally 10
    total_num_successes = 0
    total_num_trials = 0
    for i in range(num_loops):
        await train(
            task_with_answer=task_with_answer,
            max_train_trials=max_train_trials,
            max_test_trials=max_test_trials,
            task_assignment_callback=task_assignment_callback,
            reset_memory=True,
            client=client,
            page_log=page_log)
        last_response, num_successes, num_trials = await test(
            task_with_answer=task_with_answer,
            num_trials=max_test_trials,
            task_assignment_callback=task_assignment_callback,
            use_memory=True,
            reset_memory=False,
            client=client,
            page_log=page_log)

        page.add_lines("Success rate:  {}%\n".format(round((num_successes / num_trials) * 100)), flush=True)
        print("SUCCESS RATE:  {}%\n".format(round((num_successes / num_trials) * 100)))
        total_num_successes += num_successes
        total_num_trials += num_trials

    page_log.finish_page(page)
    return total_num_successes, total_num_trials


async def test_on_task_with_memory(task_index, task_assignment_callback, client, page_log, num_trials, reset_memory):
    last_response, num_successes, num_trials = await test(
        task_with_answer=define_tasks_with_answers()[task_index],
        num_trials=num_trials,
        task_assignment_callback=task_assignment_callback,
        use_memory=True,
        reset_memory=reset_memory,
        client=client,
        page_log=page_log)
    print("SUCCESS RATE:  {}%\n".format(round((num_successes / num_trials) * 100)))
    return num_successes, num_trials


async def test_on_task(task_index, task_assignment_callback, client, page_log, num_trials):
    last_response, num_successes, num_trials = await test(
        task_with_answer=define_tasks_with_answers()[task_index],
        num_trials=num_trials,
        task_assignment_callback=task_assignment_callback,
        use_memory=False,
        reset_memory=False,
        client=client,
        page_log=page_log)
    print("SUCCESS RATE:  {}%\n".format(round((num_successes / num_trials) * 100)))
    return num_successes, num_trials


async def main() -> None:
    # Create the PageLog. (This is optional)
    page_log = PageLog(PAGELOG_DIR, RUN_SUBDIR)
    page = page_log.begin_page(
        summary="main",
        details='',
        method_call="main")

    # Create the client.
    client = create_client(page_log)

    # Choose the task from those listed at the top.
    task_index = 0

    # Choose the client, agent or team to assign the task to.
    task_assignment_callback = assign_task_to_client  # assign_task_to_client or assign_task_to_magentic_one

    # Test, without using memory.
    num_successes, num_trials = await test_on_task(task_index, task_assignment_callback, client, page_log, 50)

    # Test, using memory.
    # num_successes, num_trials = await test_on_task_with_memory(task_index, task_assignment_callback, client, page_log, num_trials=3, reset_memory=True)

    # Train and test, using memory.
    # num_successes, num_trials = await train_and_test(
    #     task_index,
    #     10,  # Normally 10
    #     3,  # Normally 3
    #     task_assignment_callback,
    #     client,
    #     page_log)

    success_rate = round((num_successes / num_trials) * 100)
    page.add_lines("\nOverall success rate:  {}%\n".format(success_rate), flush=True)

    page_log.flush(final=True)  # Finalize the page log
    page_log.finish_page(page)


if __name__ == "__main__":
    asyncio.run(main())
