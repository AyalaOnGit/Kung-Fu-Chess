from __future__ import annotations
import sys
from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.factory import build_script_runner


def _read_input() -> tuple[list[str], list[str]]:
    """Read stdin and split into board lines and command lines."""
    lines = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
    board_lines, command_lines = [], []
    section = None
    for line in lines:
        if 'Board:' in line:
            section = 'board'
        elif 'Commands:' in line:
            section = 'commands'
        elif section == 'board':
            board_lines.append(line)
        elif section == 'commands':
            command_lines.append(line)
    return board_lines, command_lines


def main():
    board_lines, command_lines = _read_input()
    if not board_lines:
        return
    try:
        board = parse_board(board_lines)
    except ValueError as e:
        print(e)
        return
    _, runner = build_script_runner(board)
    for line in runner.run(command_lines):
        print(line)


if __name__ == '__main__':
    main()
