from __future__ import annotations

from enum import Enum
from estate_developer.opponent.opponent_model import OpponentModel

class OpponentStyle(Enum):
    UNKNOWN = "UNKNOWN"
    LEAN = "LEAN"
    SCALE = "SCALE"
    AGGRESSIVE = "AGGRESSIVE"


class StyleClassifier:
    """
    Infers the opponent's strategy style from their observed model.
    """

    @staticmethod
    def classify(model: OpponentModel) -> OpponentStyle:
        if not model.history:
            return OpponentStyle.UNKNOWN
        
        # Simple heuristics for V7 base
        if model.worker_count > 1 and model.tile_count > 20:
            return OpponentStyle.SCALE
        elif model.worker_count <= 1 and model.current_cash > 1000:
            return OpponentStyle.LEAN
        elif model.worker_count > 2:
            return OpponentStyle.AGGRESSIVE
            
        return OpponentStyle.UNKNOWN
