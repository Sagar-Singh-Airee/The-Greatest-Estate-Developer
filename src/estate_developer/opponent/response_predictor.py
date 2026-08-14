from __future__ import annotations

from typing import Any
from estate_developer.opponent.opponent_model import OpponentModel
from estate_developer.opponent.style_classifier import OpponentStyle, StyleClassifier
from estate_developer.state.parser import ObservationState

class ResponsePredictor:
    """
    Predicts the opponent's next actions based on their modeled style and current state.
    """

    def __init__(self):
        self.classifier = StyleClassifier()

    def predict(self, model: OpponentModel, current_state: ObservationState) -> list[dict[str, Any]]:
        """
        Returns a set of probable opponent actions for use in rollouts.
        For now, returns a baseline "PASS" response.
        In a full implementation, this should return a probability distribution of actions.
        """
        style = self.classifier.classify(model)
        
        # Simple baseline prediction for trajectory search
        predicted_actions = {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in range(model.worker_count)],
            "market": []
        }
        
        if style == OpponentStyle.SCALE and model.current_cash > 100:
             # Just an example of what they might do
             predicted_actions["market"].append(["BUY_SEED", "WHEAT", 1])
             
        return [predicted_actions]
