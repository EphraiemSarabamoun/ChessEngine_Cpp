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
print(api_key)
client = OpenAI(api_key=api_key)

# Set your Stockfish engine path (adjust if needed)
STOCKFISH_PATH = "/usr/bin/stockfish"  # update this path on your system

# Starting Elo rating for the AI (this is just an example)
INITIAL_AI_ELO = 1500

# Elo update increments for a win/loss/invalid move
ELO_WIN_INCREMENT = 50
ELO_LOSS_DECREMENT = 50

# ---------------------------
# INITIALIZE ENGINE
# ---------------------------
try:
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
except Exception as e:
    print(f"Error starting Stockfish: {e}")
    engine = None  # Engine is optional

# ---------------------------
# FUNCTION TO GET AI MOVE FROM OPENAI API
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

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10
        )
        move_str = response.choices[0].message.content.strip()
        return move_str
    except Exception as e:
        print(f"Error communicating with OpenAI API: {e}")
        return ""

# ---------------------------
# HELPER FUNCTION TO PROCESS THE AI MOVE
# ---------------------------
def process_ai_move(board: chess.Board, move_str: str, ai_elo: int):
    """
    Processes the AI's move string.
    If the move format is invalid or the move is illegal, it prints the attempted move,
    decrements the Elo, and returns (ai_elo, None, move_str).
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
# MAIN GAME LOOP
# ---------------------------
def main():
    board = chess.Board()
    ai_elo = INITIAL_AI_ELO
    failed_move_number = None  # Will store the move number at which the AI made an invalid move
    ai_move_number = 0  # Count of AI moves

    print("Welcome to Chess vs. OpenAI API!")
    print("You play White. Enter moves in Standard Algebraic Notation (e.g., e4, Nf3) or UCI (e.g., e2e4).")
    print("---------------------------------------------------\n")

    while not board.is_game_over():
        print(board)
        print("")  # empty line for readability

        if board.turn == chess.WHITE:
            # --- Human's move ---
            user_input = input("Your move: ").strip()
            try:
                # Try parsing as SAN first; if that fails, try UCI.
                try:
                    move = board.parse_san(user_input)
                except ValueError:
                    move = chess.Move.from_uci(user_input)
            except Exception:
                print("Could not parse your move. Please try again.\n")
                continue

            if move not in board.legal_moves:
                print("Illegal move. Please try again.\n")
                continue

            board.push(move)
        else:
            # --- AI's move ---
            ai_move_number += 1  # Increment count for each AI move
            print("AI is thinking...\n")
            ai_move_str = get_ai_move(board)
            print(f"OpenAI API returned: {ai_move_str}")

            ai_elo, move, attempted_move = process_ai_move(board, ai_move_str, ai_elo)
            if move is None:
                failed_move_number = ai_move_number
                break

            print(f"AI plays: {attempted_move}")

            # Optionally, evaluate the position after the move using Stockfish.
            if engine:
                try:
                    info = engine.analyse(board, chess.engine.Limit(time=0.1))
                    # The score is from White’s perspective.
                    score = info["score"].white().score(mate_score=10000)
                    print(f"Stockfish evaluation after AI move: {score} centipawns\n")
                except Exception as e:
                    print(f"Error during engine analysis: {e}\n")

    # ---------------------------
    # GAME HAS ENDED
    # ---------------------------
    print("\nGame over!")
    print(board)
    result = board.result()
    print(f"Result: {result}")

    if failed_move_number is not None:
        print(f"Invalid move occurred on GPT move number: {failed_move_number}")

    # Update AI Elo based on game result if the game ended normally.
    if result == "1-0":
        print("You win!")
        ai_elo -= ELO_LOSS_DECREMENT
    elif result == "0-1":
        print("AI wins!")
        ai_elo += ELO_WIN_INCREMENT
    else:
        print("Draw! No Elo change.")

    print(f"Final AI Elo: {ai_elo}")

# ---------------------------
# ENTRY POINT
# ---------------------------
if __name__ == '__main__':
    try:
        main()
    finally:
        if engine:
            engine.quit()