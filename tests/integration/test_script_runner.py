import unittest
from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.factory import build_script_runner


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


if __name__ == '__main__':
    unittest.main()
