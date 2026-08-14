from __future__ import annotations

from typing import Any
from estate_developer.state.parser import ObservationState
from estate_developer.simulation.rollout import rollout_plan

class PlanEvaluator:
    """
    Evaluates candidate plans by rolling them out and computing the incremental terminal value
    and the relative competitive score against the predicted opponent.
    """

    def evaluate(self, current_state: ObservationState, plan: list[dict[str, Any]]) -> float:
        """
        Computes a scalar score for a candidate plan.
        
        Currently computes a simple terminal cash delta.
        A full implementation should use:
        ΔTerminalValue(action) = TerminalValue(after plan) - TerminalValue(if we don't take plan)
        """
        if not plan:
            return 0.0
            
        final_state = rollout_plan(current_state, plan)
        
        # Simple terminal value proxy: cash difference
        # In reality, this should factor in crop value, opponent cash, and win probability.
        return final_state.me.money - current_state.me.money
