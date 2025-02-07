import chess
import chess.engine
from openai import OpenAI
import os
from dotenv import load_dotenv


load_dotenv()  # load environment variables from .env
api_key = os.getenv("OPENAI_API_KEY")
print("API key:", api_key)
client = OpenAI(api_key=api_key)

# Set Stockfish engine path 
STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"

try:
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
except Exception as e:
    print(f"Error starting Stockfish: {e}")
    engine = None  # Engine is optional

def get_ai_move(board: chess.Board) -> str:
    fen = board.fen()
    prompt = (
        "You are a chess engine. Given the following chess position in FEN format:\n\n"
        f"{fen}\n\n"
        "Please reply with the best move in UCI notation (e.g. e2e4) and nothing else."
    )

    # try:
    #     response = client.chat.completions.create(
    #         model="o1-preview",
    #         # model="o1-preview",
    #         # model="gpt-4-turbo",
    #         # model="gpt-3.5-turbo",
    #         messages=[{"role": "user", "content": prompt}],
    #         temperature=1,
    #         max_completion_tokens=1000
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
        #     # model="gpt-4o-mini",
        #     # model="gpt-4-turbo",
        #     # model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100
        )
        move_str = response.choices[0].message.content.strip()
        return move_str
    except Exception as e:
        print(f"Error communicating with OpenAI API: {e}")
        return ""

def process_ai_move(board: chess.Board, move_str: str):
    try:
        move = chess.Move.from_uci(move_str)
    except Exception:
        print(f"ERROR: The move format '{move_str}' is invalid. AI loses by default.")
        print(f"Attempted move: {move_str}")
        return  None, move_str

    if move not in board.legal_moves:
        print(f"ERROR: The move '{move_str}' is illegal in the current position. AI loses by default.")
        print(f"Attempted move: {move_str}")
        return  None, move_str

    board.push(move)
    return move, move_str

def simulate_game():
    board = chess.Board()
    failed_move_number = None
    ai_move_number = 0  # Counts the number of moves GPT (Black) makes

    # Continue until game over
    while not board.is_game_over():
        if board.turn == chess.WHITE:
            # White's move from Stockfish engine
            try:
                result = engine.play(board, chess.engine.Limit(time=2.0))
                board.push(result.move)
            except Exception as e:
                print(f"Error in engine move: {e}")
                break
        else:
            # GPT's move as Black
            ai_move_number += 1
            ai_move_str = get_ai_move(board)
            print(f"GPT (Black) move {ai_move_number}: {ai_move_str}")
            move, attempted_move = process_ai_move(board, ai_move_str)
            if move is None:
                failed_move_number = ai_move_number
                break
            print(f"GPT plays: {attempted_move}")

            # Optional: evaluate position after GPT move using Stockfish
            if engine:
                try:
                    info = engine.analyse(board, chess.engine.Limit(time=0.5))
                    score = info["score"].white().score(mate_score=10000)
                    print(f"Stockfish evaluation after GPT move: {score} centipawns\n")
                except Exception as e:
                    print(f"Error during engine analysis: {e}\n")

    # Determine game result.
    # If GPT made an invalid move, we force the result to be a loss ("1-0").
    result = board.result()
    if failed_move_number is not None:
        result = "1-0"
    if result == "1-0":
        print("Result: White wins (GPT loses).")
    elif result == "0-1":
        print("Result: GPT wins!")
    else:
        print("Result: Draw!")

    return result, failed_move_number, board

def simulate_games(num_games: int):
    wins = 0
    losses = 0
    draws = 0
    invalid_moves = 0

    # Dictionary to accumulate invalid move numbers and their frequency.
    invalid_move_distribution = {}

    for i in range(num_games):
        print(f"\n=== Starting Game {i+1} ===")
        result, failed_move_number, board = simulate_game()
        print(board)
        print(f"Game {i+1} result: {result}")

        if failed_move_number is not None:
            print(f"GPT made an invalid move on move number {failed_move_number}")
            invalid_moves += 1
            invalid_move_distribution[failed_move_number] = invalid_move_distribution.get(failed_move_number, 0) + 1

        if result == "0-1":  # GPT wins as Black
            wins += 1
        elif result == "1-0":  # GPT loses
            losses += 1
        else:
            draws += 1


    print("\n=== Simulation Complete ===")
    print(f"Total games: {num_games}")
    print(f"Wins: {wins}, Losses: {losses}, Draws: {draws}, Invalid moves: {invalid_moves}")
    print("\nInvalid move distribution (move number : count):")
    for move_number in sorted(invalid_move_distribution.keys()):
        print(f"  {move_number}: {invalid_move_distribution[move_number]}")

# ---------------------------
# ENTRY POINT
# ---------------------------
if __name__ == '__main__':
    try:
        # For example, simulate 25 games:
        simulate_games(1)
    finally:
        if engine:
            engine.quit()