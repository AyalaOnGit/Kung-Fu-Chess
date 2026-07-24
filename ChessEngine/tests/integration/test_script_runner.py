import unittest
from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.engine_builder import build_script_runner
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import PieceState


class TestScriptRunner(unittest.TestCase):
    def test_move_and_print(self):
        b = parse_board(["wR . . .", ". . . ."])
        _, runner = build_script_runner(b)
        output = runner.run([
            "click 50 50",
            "click 350 50",
            "wait 3000",
            "print board",
        ])
        self.assertEqual(output[0], ". . . wR")

    def test_game_over_after_king_capture(self):
        b = parse_board(["wR bK", ". ."])
        engine, runner = build_script_runner(b)
        runner.run(["click 50 50", "click 150 50", "wait 1000"])
        self.assertTrue(engine.game_over)

    def test_blank_line_is_skipped(self):
        b = parse_board(["wR .", ". ."])
        _, runner = build_script_runner(b)
        output = runner.run(["", "print board"])
        self.assertEqual(output[0], "wR .")

    def test_jump_command_executes_via_script(self):
        b = parse_board(["wR .", ". ."])
        engine, runner = build_script_runner(b)
        runner.run(["jump 50 50"])
        self.assertEqual(engine.board.piece_at(Position(0, 0)).state, PieceState.JUMPING)


if __name__ == '__main__':
    unittest.main()
