from io_parser import read_and_parse_input
from validator import validate_board
from game_engine import execute_game_logic

def main():
    # 1. קריאה ופירוק הקלט
    board_lines, commands = read_and_parse_input()
    
    if not board_lines:
        return

    # 2. אימות הלוח
    is_valid, result = validate_board(board_lines)
    if not is_valid:
        print(result)
        return

    # 3. הרצת המשחק
    execute_game_logic(commands, board_lines, result)

if __name__ == "__main__":
    main()