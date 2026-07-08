import sys


def read_and_parse_input():
    """
    Read all of stdin and split it into board lines and command lines.

    Expects the input to contain a 'Board:' section followed by a 'Commands:' section.
    Lines belonging to each section are collected until the next section header or EOF.
    Empty lines are ignored throughout.

    :return: (board_lines, command_lines) — two lists of stripped strings.
    """
    input_text = sys.stdin.read()
    lines = [line.strip() for line in input_text.splitlines()]

    board_lines = []
    commands = []
    in_board = False
    in_commands = False

    for line in lines:
        if not line:
            continue
        if "Board:" in line:
            in_board = True
            in_commands = False
            continue
        if "Commands:" in line:
            in_board = False
            in_commands = True
            continue

        if in_board:
            board_lines.append(line)
        elif in_commands:
            commands.append(line)

    return board_lines, commands
