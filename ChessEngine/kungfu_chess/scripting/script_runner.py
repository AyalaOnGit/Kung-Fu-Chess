from __future__ import annotations
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.engine.commands import CommandResult
from kungfu_chess.interaction.controller import Controller
from kungfu_chess.io.board_printer import board_to_lines


class ScriptRunner:
    """
    Text test runner: interprets a command script and drives the public API.

    Supported commands:
      click <x> <y>
      jump <x> <y>
      wait <ms>
      print board

    Does not duplicate game logic, mutate Board directly, or know movement rules.
    """

    def __init__(self, engine: GameEngine, controller: Controller):
        self._engine     = engine
        self._controller = controller

    def run(self, lines: list[str]) -> list[str]:
        """
        Execute all commands and return captured 'print board' output lines.

        :param lines: List of command strings.
        :return: All lines printed by 'print board' commands.
        """
        output = []
        for line in lines:
            parts = line.split()
            if not parts:
                continue
            cmd = parts[0]
            if cmd == 'click' and len(parts) == 3:
                self._controller.on_click(int(parts[1]), int(parts[2]))
            elif cmd == 'jump' and len(parts) == 3:
                self._controller.on_jump(int(parts[1]), int(parts[2]))
            elif cmd == 'wait' and len(parts) == 2:
                self._engine.wait(int(parts[1]))
            elif line.strip() == 'print board':
                output.extend(board_to_lines(self._engine.board))
        return output
