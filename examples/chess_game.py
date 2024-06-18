"""This is an example of simulating a chess game with two agents
that play against each other, using tools to reason about the game state
and make moves, and using a group chat manager to orchestrate the conversation."""

import argparse
import asyncio
import logging
from typing import Annotated, Literal

from agnext.application import SingleThreadedAgentRuntime
from agnext.chat.agents.chat_completion_agent import ChatCompletionAgent
from agnext.chat.memory import BufferedChatMemory
from agnext.chat.patterns.group_chat_manager import GroupChatManager
from agnext.chat.types import TextMessage
from agnext.components.models import OpenAI, SystemMessage
from agnext.components.tools import FunctionTool
from agnext.core import AgentRuntime
from chess import BLACK, SQUARE_NAMES, WHITE, Board, Move
from chess import piece_name as get_piece_name


def validate_turn(board: Board, player: Literal["white", "black"]) -> None:
    """Validate that it is the player's turn to move."""
    last_move = board.peek() if board.move_stack else None
    if last_move is not None:
        if player == "white" and board.color_at(last_move.to_square) == WHITE:
            raise ValueError("It is not your turn to move. Wait for black to move.")
        if player == "black" and board.color_at(last_move.to_square) == BLACK:
            raise ValueError("It is not your turn to move. Wait for white to move.")
    elif last_move is None and player != "white":
        raise ValueError("It is not your turn to move. Wait for white to move first.")


def get_legal_moves(
    board: Board, player: Literal["white", "black"]
) -> Annotated[str, "A list of legal moves in UCI format."]:
    """Get legal moves for the given player."""
    validate_turn(board, player)
    legal_moves = list(board.legal_moves)
    if player == "black":
        legal_moves = [move for move in legal_moves if board.color_at(move.from_square) == BLACK]
    elif player == "white":
        legal_moves = [move for move in legal_moves if board.color_at(move.from_square) == WHITE]
    else:
        raise ValueError("Invalid player, must be either 'black' or 'white'.")
    if not legal_moves:
        return "No legal moves. The game is over."

    return "Possible moves are: " + ", ".join([move.uci() for move in legal_moves])


def get_board(board: Board) -> str:
    return str(board)


def make_move(
    board: Board,
    player: Literal["white", "black"],
    thinking: Annotated[str, "Thinking for the move."],
    move: Annotated[str, "A move in UCI format."],
) -> Annotated[str, "Result of the move."]:
    """Make a move on the board."""
    validate_turn(board, player)
    newMove = Move.from_uci(move)
    board.push(newMove)

    # Print the move.
    print("-" * 50)
    print("Player:", player)
    print("Move:", newMove.uci())
    print("Thinking:", thinking)
    print("Board:")
    print(board.unicode(borders=True))

    # Get the piece name.
    piece = board.piece_at(newMove.to_square)
    assert piece is not None
    piece_symbol = piece.unicode_symbol()
    piece_name = get_piece_name(piece.piece_type)
    if piece_symbol.isupper():
        piece_name = piece_name.capitalize()
    return f"Moved {piece_name} ({piece_symbol}) from {SQUARE_NAMES[newMove.from_square]} to {SQUARE_NAMES[newMove.to_square]}."


def chess_game(runtime: AgentRuntime) -> None:  # type: ignore
    """Create agents for a chess game and return the group chat."""

    # Create the board.
    board = Board()

    # Create tools for each player.
    # @functools.wraps(get_legal_moves)
    def get_legal_moves_black() -> str:
        return get_legal_moves(board, "black")

    # @functools.wraps(get_legal_moves)
    def get_legal_moves_white() -> str:
        return get_legal_moves(board, "white")

    # @functools.wraps(make_move)
    def make_move_black(
        thinking: Annotated[str, "Thinking for the move"],
        move: Annotated[str, "A move in UCI format"],
    ) -> str:
        return make_move(board, "black", thinking, move)

    # @functools.wraps(make_move)
    def make_move_white(
        thinking: Annotated[str, "Thinking for the move"],
        move: Annotated[str, "A move in UCI format"],
    ) -> str:
        return make_move(board, "white", thinking, move)

    def get_board_text() -> Annotated[str, "The current board state"]:
        return get_board(board)

    black_tools = [
        FunctionTool(
            get_legal_moves_black,
            name="get_legal_moves",
            description="Get legal moves.",
        ),
        FunctionTool(
            make_move_black,
            name="make_move",
            description="Make a move.",
        ),
        FunctionTool(
            get_board_text,
            name="get_board",
            description="Get the current board state.",
        ),
    ]

    white_tools = [
        FunctionTool(
            get_legal_moves_white,
            name="get_legal_moves",
            description="Get legal moves.",
        ),
        FunctionTool(
            make_move_white,
            name="make_move",
            description="Make a move.",
        ),
        FunctionTool(
            get_board_text,
            name="get_board",
            description="Get the current board state.",
        ),
    ]

    black = runtime.register_and_get(
        "PlayerBlack",
        lambda: ChatCompletionAgent(
            description="Player playing black.",
            system_messages=[
                SystemMessage(
                    content="You are a chess player and you play as black. "
                    "Use get_legal_moves() to get list of legal moves. "
                    "Use get_board() to get the current board state. "
                    "Think about your strategy and call make_move(thinking, move) to make a move."
                ),
            ],
            memory=BufferedChatMemory(buffer_size=10),
            model_client=OpenAI(model="gpt-4-turbo"),
            tools=black_tools,
        ),
    )
    white = runtime.register_and_get(
        "PlayerWhite",
        lambda: ChatCompletionAgent(
            description="Player playing white.",
            system_messages=[
                SystemMessage(
                    content="You are a chess player and you play as white. "
                    "Use get_legal_moves() to get list of legal moves. "
                    "Use get_board() to get the current board state. "
                    "Think about your strategy and call make_move(thinking, move) to make a move."
                ),
            ],
            memory=BufferedChatMemory(buffer_size=10),
            model_client=OpenAI(model="gpt-4-turbo"),
            tools=white_tools,
        ),
    )
    # Create a group chat manager for the chess game to orchestrate a turn-based
    # conversation between the two agents.
    runtime.register(
        "ChessGame",
        lambda: GroupChatManager(
            description="A chess game between two agents.",
            runtime=runtime,
            memory=BufferedChatMemory(buffer_size=10),
            participants=[white, black],  # white goes first
        ),
    )


async def main() -> None:
    runtime = SingleThreadedAgentRuntime()
    chess_game(runtime)
    # Publish an initial message to trigger the group chat manager to start orchestration.
    runtime.publish_message(TextMessage(content="Game started.", source="System"), namespace="default")
    while True:
        await runtime.process_next()
        await asyncio.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a chess game between two agents.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.WARNING)
        logging.getLogger("agnext").setLevel(logging.DEBUG)
        handler = logging.FileHandler("chess_game.log")
        logging.getLogger("agnext").addHandler(handler)

    asyncio.run(main())
