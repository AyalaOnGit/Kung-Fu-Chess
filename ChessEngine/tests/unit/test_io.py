import contextlib
import io
import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.board import Board
from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.io.board_printer import board_to_lines, print_board
from kungfu_chess.io.board_factory import standard_board


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

    def test_empty_definition_raises(self):
        with self.assertRaises(ValueError):
            parse_board([])

    def test_all_blank_lines_raises(self):
        with self.assertRaises(ValueError):
            parse_board(["", "   "])


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

    def test_print_board_writes_lines_to_stdout(self):
        b = parse_board(["wR .", ". bK"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_board(b)
        self.assertEqual(buf.getvalue().splitlines(), ["wR .", ". bK"])


class TestBoardFactory(unittest.TestCase):
    def test_standard_board_dimensions(self):
        b = standard_board()
        self.assertEqual(b.width, 8)
        self.assertEqual(b.height, 8)

    def test_standard_board_places_kings_correctly(self):
        b = standard_board()
        self.assertEqual(b.piece_at(Position(7, 4)).token(), 'wK')
        self.assertEqual(b.piece_at(Position(0, 4)).token(), 'bK')

    def test_standard_board_back_ranks(self):
        b = standard_board()
        expected = ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
        for col, kind_letter in enumerate(expected):
            self.assertEqual(b.piece_at(Position(0, col)).token(), 'b' + kind_letter)
            self.assertEqual(b.piece_at(Position(7, col)).token(), 'w' + kind_letter)

    def test_standard_board_pawn_rows(self):
        b = standard_board()
        for col in range(8):
            self.assertEqual(b.piece_at(Position(1, col)).token(), 'bP')
            self.assertEqual(b.piece_at(Position(6, col)).token(), 'wP')

    def test_standard_board_middle_rows_empty(self):
        b = standard_board()
        for row in range(2, 6):
            for col in range(8):
                self.assertIsNone(b.piece_at(Position(row, col)))


if __name__ == '__main__':
    unittest.main()
