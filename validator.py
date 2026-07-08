from config import PIECE_CONFIG, VALID_COLORS


def validate_board(board_lines):
    """
    Validate the raw board lines for structural and token correctness.

    Checks that all rows have the same width and that every token is either
    an empty cell ('.') or a valid two-character piece token (color + type).

    :param board_lines: List of strings, each representing one board row.
    :return: (True, width) on success, or (False, error_message) on failure.
    """
    if not board_lines:
        return True, 0

    valid_pieces = set(PIECE_CONFIG.keys())
    expected_width = None

    for line in board_lines:
        tokens = line.split()
        if expected_width is None:
            expected_width = len(tokens)
        elif len(tokens) != expected_width:
            return False, "ERROR ROW_WIDTH_MISMATCH"

        for token in tokens:
            if token == '.':
                continue
            if len(token) == 2 and token[0] in VALID_COLORS and token[1] in valid_pieces:
                continue
            return False, "ERROR UNKNOWN_TOKEN"

    return True, expected_width
