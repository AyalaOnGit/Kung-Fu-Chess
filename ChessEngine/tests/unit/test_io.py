import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.board import Board
from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.io.board_printer import board_to_lines


class TestBoardParser(unittest.TestCase):
    def test_parses_valid_board(self):
        b = parse_board(["wR . bK", ". . ."])
        self.assertIsNotNone(b.piece_at(Position(0, 0)))
        self.assertIsNone(b.piece_at(Position(0, 1)))
        self.assertIsNotNone(b.piece_at(Position(0, 2)))

    def test_dimensions(self):
        b = parse_board(["wR . bK", ". . ."])
        self.assertEqual(b.width, 3)
        self.assertEqual(b.height, 2)

    def test_unknown_token_raises(self):
        with self.assertRaises(ValueError):
            parse_board(["wR xZ"])

    def test_row_width_mismatch_raises(self):
        with self.assertRaises(ValueError):
            parse_board(["wR .", ". . ."])


class TestBoardPrinter(unittest.TestCase):
    def test_prints_correct_tokens(self):
        b = parse_board(["wR .", ". bK"])
        lines = board_to_lines(b)
        self.assertEqual(lines[0], "wR .")
        self.assertEqual(lines[1], ". bK")

    def test_empty_board(self):
        b = Board(width=2, height=2)
        lines = board_to_lines(b)
        self.assertEqual(lines, [". .", ". ."])


if __name__ == '__main__':
    unittest.main()
