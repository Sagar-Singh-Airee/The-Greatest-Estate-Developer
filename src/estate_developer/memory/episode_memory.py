from __future__ import annotations

class EpisodeMemory:
    """
    Stores state fingerprints, decisions, and actual outcomes for later learning and calibration.
    """

    def __init__(self):
        self.history: list[dict] = []

    def record_decision(self, step: int, state_summary: dict, predicted_value: float, decision: dict):
        """
        Records a decision made by the planner.
        """
        self.history.append({
            "step": step,
            "state_summary": state_summary,
            "predicted_value": predicted_value,
            "decision": decision,
            "actual_result": None,
            "error": None
        })

    def update_result(self, step: int, actual_result: float):
        """
        Updates the memory with the actual result to compute prediction error.
        """
        for record in self.history:
            if record["step"] == step:
                record["actual_result"] = actual_result
                record["error"] = actual_result - record["predicted_value"]
                break
