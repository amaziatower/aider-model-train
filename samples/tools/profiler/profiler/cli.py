import argparse
import json

from tqdm import tqdm

from .profiler import Profiler
from .message import Message
from .llm import OpenAIJSONService
from .utils import parse_agb_console
from .agb import AGB_STATE_SPACE


def profile(args):
    if args.file:
        with open(args.file, "r") as f:
            chat_history_json = json.load(f)
            try:
                chat_history = [Message(**message) for message in chat_history_json]
            except Exception:
                print(
                    """Error parsing chat history. Please provide a file containing a list of JSON objects with the following keys: source, role, content."""
                )
                exit(1)
            profiler = Profiler(llm_service=OpenAIJSONService())

    elif args.json:
        chat_history_json = json.loads(args.json)
        chat_history = [Message(**message) for message in chat_history_json]
        profiler = Profiler(llm_service=OpenAIJSONService())

    elif args.agbconsole:
        chat_history = parse_agb_console(args.agbconsole)
        profiler = Profiler(state_space=AGB_STATE_SPACE, llm_service=OpenAIJSONService())

    else:
        print("Please provide either a file or JSON string containing chat messages.")
        exit(1)

    jsonl_file = open(args.o, "w") if args.o else None

    msg_idx = 0
    for message in tqdm(chat_history, desc="Profiling messages", unit="message"):
        profile = profiler.profile_message(message)
        state_names = [s.name for s in profile.states]
        sorted_state_names = sorted(state_names)

        raw_content = message.content[:40].encode("unicode_escape").decode()

        tqdm.write(f"[{msg_idx}] {message.source}: {raw_content}")
        for sname in sorted_state_names:
            tqdm.write(f"\t{sname}")

        if jsonl_file:
            jsonl_file.write(json.dumps(profile.to_dict()) + "\n")

        msg_idx += 1


def visualize(args):
    print("Visualizing profile...")


def main():
    parser = argparse.ArgumentParser(description="Profile and visualize messages between multiple agents.")
    subparsers = parser.add_subparsers(dest="command")

    # Profile command
    profile_parser = subparsers.add_parser(
        "profile",
        description="Profile a set of chat messages. Uses an LLM to select the states that apply to each agent message.",
        help="profile a set of chat messages.",
    )
    profile_parser.add_argument("--file", type=str, help="read from a JSON file containing chat messages.")
    profile_parser.add_argument("--json", type=str, help="read from A JSON string containing chat messages.")
    profile_parser.add_argument("--agbconsole", type=str, help="read from a console file generated by autogenbench.")
    profile_parser.add_argument("--o", type=str, help="create a JSONL file with the profile.")

    # Visualize command
    visualize_parser = subparsers.add_parser(
        "visualize",
        description="Visualize a profile. Creates a directed graph of the states that apply to a message.",
        help="visualize a profile.",
    )
    visualize_parser.add_argument("--jsonl", type=bool, help="Read profile from a JSONL containing profile.")
    visualize_parser.add_argument("--o", type=str, help="Output the visualization to the given path.")

    args = parser.parse_args()

    # If no arguments were provided, print the help message and exit.
    if not any(vars(args).values()):
        parser.print_help()
        exit(1)

    if args.command == "profile":
        if args.file is None and args.json is None and args.agbconsole is None:
            profile_parser.print_help()
            exit(1)
        profile(args)
    elif args.command == "visualize":
        if args.jsonl is None:
            visualize_parser.print_help()
            exit(1)
        visualize(args)
