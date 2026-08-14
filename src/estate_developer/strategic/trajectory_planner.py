from __future__ import annotations

from typing import Any
from estate_developer.state.parser import ObservationState
from estate_developer.opponent.opponent_model import OpponentModel
from estate_developer.planning.beam_search import BeamSearchPlanner
from estate_developer.planning.endgame_planner import EndgamePlanner
from estate_developer.strategic.policy_guard import PolicyGuard
from estate_developer.economics.market_manager import MarketManager


class StrategicTrajectoryPlanner:
    """
    The main strategic meta-controller. Coordinates the simulator, search, and opponent model
    to produce the best trajectory and extract the immediate next actions.
    """

    def __init__(self):
        self.beam_search = BeamSearchPlanner()
        self.endgame = EndgamePlanner()
        self.guard = PolicyGuard()
        self.market_manager = MarketManager()

    def plan(self, state: ObservationState, opponent_model: OpponentModel) -> dict[str, Any]:
        """
        Determines the best actions to take for the current step.
        """
        if self.endgame.is_endgame(state):
            trajectory = self.endgame.plan_liquidation(state)
        else:
            # We would normally incorporate the opponent_model into the search here
            trajectory = self.beam_search.plan(state)
            
        if not trajectory:
            return {"farmer": ["PASS"], "hands": [], "market": []}
            
        next_actions = trajectory[0]
        
        # Inject strategic market orders (selling optimally)
        sell_orders = self.market_manager.get_optimal_sell_orders(
            state, opponent_model=opponent_model,
        )
        # Filter out naive sell orders from beam search that just dump inventory
        filtered_market = [order for order in next_actions.get("market", []) if order[0] != "SELL"]
        next_actions["market"] = filtered_market + sell_orders
        
        # Ensure we don't violate hard constraints
        self.guard.enforce(state, next_actions)
        
        return next_actions
