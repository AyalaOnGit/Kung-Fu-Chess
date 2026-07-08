from chess_pieces import KingMovement, KnightMovement, LinearMovement, PawnMovement


class PieceMovementFactory:
    """
    Registry that maps piece-type characters to their MovementStrategy instances.

    Supports runtime registration of custom strategies to allow user-defined piece types.
    """

    _strategies = {
        'K': KingMovement(),
        'N': KnightMovement(),
        'R': LinearMovement(allow_straight=True, allow_diagonal=False),
        'B': LinearMovement(allow_straight=False, allow_diagonal=True),
        'Q': LinearMovement(allow_straight=True, allow_diagonal=True),
        'P': PawnMovement(),
    }

    @classmethod
    def get_strategy(cls, piece_type):
        """
        Return the MovementStrategy for the given piece-type character, or None if unknown.

        :param piece_type: Single character identifying the piece type (e.g. 'R', 'P').
        """
        return cls._strategies.get(piece_type)

    @classmethod
    def register_strategy(cls, piece_type, strategy):
        """
        Register or replace the MovementStrategy for a piece-type character.

        Use this to add custom piece types for user-defined games.

        :param piece_type: Single character identifying the piece type.
        :param strategy: A MovementStrategy instance to associate with this type.
        """
        cls._strategies[piece_type] = strategy
