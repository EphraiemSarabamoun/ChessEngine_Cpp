import chess
import chess.engine
from openai import OpenAI
import os
from dotenv import load_dotenv

# ---------------------------
# CONFIGURATION
# ---------------------------
load_dotenv()  # load environment variables from .env
api_key = os.getenv("OPENAI_API_KEY")
print("API key:", api_key)
client = OpenAI(api_key=api_key)

# Set your Stockfish engine path (adjust if needed)
# Make sure to point to the actual binary.
STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"

# Starting Elo rating for the AI (this is just an example)
INITIAL_AI_ELO = 1500

# Elo update increments for a win/loss/invalid move
ELO_WIN_INCREMENT = 50
ELO_LOSS_DECREMENT = 50

# ---------------------------
# INITIALIZE STOCKFISH ENGINE
# ---------------------------
try:
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
except Exception as e:
    print(f"Error starting Stockfish: {e}")
    engine = None  # Engine is optional

# ---------------------------
# FUNCTION TO GET AI MOVE FROM OPENAI API (GPT as Black)
# ---------------------------
def get_ai_move(board: chess.Board) -> str:
    """
    Ask the OpenAI API for the best move given the current board position.
    The prompt instructs the model to return only a UCI-formatted move (e.g. 'e2e4').
    """
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

# ---------------------------
# HELPER FUN CTION TO PROCESS THE AI MOVE
# ---------------------------
def process_ai_move(board: chess.Board, move_str: str, ai_elo: int):
    """
    Processes GPT's move string.
    If the move format is invalid or the move is illegal,
    it prints the attempted move, decrements the Elo, and returns (ai_elo, None, move_str).
    Otherwise, it pushes the move to the board and returns (ai_elo, move, move_str).
    """
    try:
        move = chess.Move.from_uci(move_str)
    except Exception:
        print(f"ERROR: The move format '{move_str}' is invalid. AI loses by default.")
        ai_elo -= ELO_LOSS_DECREMENT
        print(f"Attempted move: {move_str}")
        return ai_elo, None, move_str

    if move not in board.legal_moves:
        print(f"ERROR: The move '{move_str}' is illegal in the current position. AI loses by default.")
        ai_elo -= ELO_LOSS_DECREMENT
        print(f"Attempted move: {move_str}")
        return ai_elo, None, move_str

    board.push(move)
    return ai_elo, move, move_str

# ---------------------------
# SIMULATE A SINGLE GAME
# ---------------------------
def simulate_game(current_elo: int):
    """
    Simulate one game of chess with Stockfish playing White and GPT playing Black.
    Returns:
      - result: final board result (e.g. "1-0", "0-1", or "*")
      - updated Elo rating
      - failed_move_number: move number at which GPT made an invalid move (or None)
      - final board state
    """
    board = chess.Board()
    ai_elo = current_elo
    failed_move_number = None
    ai_move_number = 0  # Counts the number of moves GPT (Black) makes

    # Continue until game over
    while not board.is_game_over():
        if board.turn == chess.WHITE:
            # White's move from Stockfish (use longer search time for dynamic moves)
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
            ai_elo, move, attempted_move = process_ai_move(board, ai_move_str, ai_elo)
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

    # Update Elo based on game result.
    if result == "1-0":
        print("Result: White wins (GPT loses).")
        ai_elo -= ELO_LOSS_DECREMENT
    elif result == "0-1":
        print("Result: GPT wins!")
        ai_elo += ELO_WIN_INCREMENT
    else:
        print("Result: Draw!")
        # No Elo change on draw

    return result, ai_elo, failed_move_number, board

# ---------------------------
# SIMULATE MULTIPLE GAMES
# ---------------------------
def simulate_games(num_games: int):
    current_elo = INITIAL_AI_ELO
    wins = 0
    losses = 0
    draws = 0
    invalid_moves = 0

    # Dictionary to accumulate invalid move numbers and their frequency.
    invalid_move_distribution = {}

    for i in range(num_games):
        print(f"\n=== Starting Game {i+1} ===")
        result, current_elo, failed_move_number, board = simulate_game(current_elo)
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

        print(f"Current Elo after game {i+1}: {current_elo}")

    print("\n=== Simulation Complete ===")
    print(f"Total games: {num_games}")
    print(f"Wins: {wins}, Losses: {losses}, Draws: {draws}, Invalid moves: {invalid_moves}")
    print(f"Final Elo: {current_elo}")
    print("\nInvalid move distribution (move number : count):")
    for move_number in sorted(invalid_move_distribution.keys()):
        print(f"  {move_number}: {invalid_move_distribution[move_number]}")

# ---------------------------
# ENTRY POINT
# ---------------------------
if __name__ == '__main__':
    try:
        # For example, simulate 100 games:
        simulate_games(25)
    finally:
        if engine:
            engine.quit()