from game_state import GameState
from commands import WaitCommand, PrintBoardCommand, JumpCommand, ClickCommand


def execute_game_logic(commands_lines, board_lines, expected_width):
    """
    Initialize the game state and execute a sequence of commands against it.

    Parses each command line into the appropriate Command object and runs it.
    Unknown or malformed command lines are silently skipped.

    :param commands_lines: List of raw command strings (e.g. ['click 50 50', 'wait 1000']).
    :param board_lines: List of raw board row strings used to build the initial GameState.
    :param expected_width: Number of columns the board is expected to have.
    """
    state = GameState(board_lines, expected_width)
    context = {'selected': None}

    for line in commands_lines:
        parts = line.split()
        if not parts:
            continue

        cmd_type = parts[0]
        command = None

        if cmd_type == "wait" and len(parts) == 2:
            command = WaitCommand(int(parts[1]))
        elif line == "print board":
            command = PrintBoardCommand()
        elif cmd_type == "jump" and len(parts) == 3:
            command = JumpCommand(int(parts[1]), int(parts[2]))
        elif cmd_type == "click" and len(parts) == 3:
            command = ClickCommand(int(parts[1]), int(parts[2]))

        if command:
            command.execute(state, context)
