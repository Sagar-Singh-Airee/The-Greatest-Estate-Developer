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
    The main strategic meta-controller. Coordinates the simulator, search, and
    opponent model to produce the best trajectory and extract immediate actions.

    Plan Caching:
        The beam search produces a multi-step action sequence (up to max_depth=3).
        We cache that plan and execute one action per game step without replanning.
        We replan only when:
            - The plan cache is empty (plan exhausted).
            - State diverges significantly from expectations (money changed
              unexpectedly or a tile we expected to be free is occupied).
    """

    def __init__(self):
        self.beam_search = BeamSearchPlanner()
        self.endgame = EndgamePlanner()
        self.guard = PolicyGuard()
        self.market_manager = MarketManager()

        # ---- Plan cache ----
        self._plan_cache: list[dict[str, Any]] = []
        self._last_money: float | None = None
        self._last_step: int = -1

    # ================================================================
    # DIVERGENCE DETECTION
    # ================================================================

    def _state_diverged(self, state: ObservationState) -> bool:
        """
        Returns True if the observed state differs enough from our expectation
        that we should discard the cached plan and replan.

        Triggers:
            - A step was skipped (shouldn't happen but guards against it).
            - Our money changed more than expected (market/harvest occurred
              outside our plan — e.g. opponent sold and price fell).
        """
        # Always replan on first call
        if self._last_step == -1:
            return True

        # Skipped a step — stale cache
        if state.step != self._last_step + 1:
            return True

        # Unexpected large money change (±2000 coins outside our market orders)
        # Old threshold of 600 caused replanning on every sell, wasting compute.
        if self._last_money is not None:
            delta = abs(state.me.money - self._last_money)
            if delta > 2000:
                return True

        return False

    # ================================================================
    # PLAN MANAGEMENT
    # ================================================================

    def _build_new_plan(
        self,
        state: ObservationState,
        opponent_model: OpponentModel,
    ) -> list[dict[str, Any]]:
        """Run beam search and return the full action sequence."""
        return self.beam_search.plan(state, opponent_model=opponent_model)

    def _inject_market_orders(
        self,
        state: ObservationState,
        action: dict[str, Any],
        opponent_model: OpponentModel,
    ) -> dict[str, Any]:
        """
        Overlay optimal market orders onto an action dict.
        - Removes naive SELL orders from beam search.
        - Injects MarketManager's optimal SELL orders (price-timed).
        - Injects arbitrage BUY_PRODUCT orders (shop demand exploitation).
        - Injects emergency WHEAT buys if animals need feeding.
        """
        sell_orders = self.market_manager.get_optimal_sell_orders(
            state,
            opponent_model=opponent_model,
        )
        buy_orders = self.market_manager.get_optimal_buy_orders(
            state,
            opponent_model=opponent_model,
        )
        # Remove naive SELL orders; keep BUY_SEED / BUY_ANIMAL / HIRE / BUY_LAND
        filtered_market = [
            order
            for order in action.get("market", [])
            if order[0] not in ("SELL", "BUY_PRODUCT")
        ]
        action = dict(action)
        # Market orders execute in list order. Selling first lets the same
        # turn's proceeds fund expansion and avoids rejecting a valid buy
        # before its financing order is processed.
        action["market"] = sell_orders + filtered_market + buy_orders
        return action

    # ================================================================
    # MAIN PLANNING ENTRY POINT
    # ================================================================

    def plan(
        self,
        state: ObservationState,
        opponent_model: OpponentModel,
    ) -> dict[str, Any]:
        """
        Returns the best action for the current game step.

        On cache hit  → pops the next action from the cached plan.
        On cache miss → runs beam search, caches the result, pops the first.
        """

        # ---- Endgame override (never cache; liquidation is bespoke each step)
        if self.endgame.is_endgame(state):
            trajectory = self.endgame.plan_liquidation(state)
            self._plan_cache = []   # discard any cached plan
            if not trajectory:
                return {"farmer": ["PASS"], "hands": [], "market": []}

            next_action = trajectory[0]
            self.guard.enforce(state, next_action)
            self._last_step = state.step
            self._last_money = state.me.money
            return next_action

        # ---- Divergence check — discard stale cache
        if self._state_diverged(state) or not self._plan_cache:
            self._plan_cache = self._build_new_plan(state, opponent_model)

        # ---- Pop the next action from cache
        if self._plan_cache:
            next_action = self._plan_cache.pop(0)
        else:
            next_action = {"farmer": ["PASS"], "hands": [], "market": []}

        # ---- Overlay optimal market orders (sell + buy arbitrage)
        next_action = self._inject_market_orders(state, next_action, opponent_model)

        # ---- Hard-constraint enforcement
        self.guard.enforce(state, next_action)

        # ---- PASS-killer: farmer should NEVER idle when work exists.
        # If the beam search returned PASS for the farmer, override with the
        # best available physical action (water, harvest, dig, feed, etc.)
        if next_action.get("farmer") in (["PASS"], None, []):
            from estate_developer.planning.scheduler import TaskScheduler
            _sched = TaskScheduler()
            _physical = _sched._best_physical_action(state)
            if _physical and _physical != ["PASS"]:
                next_action = dict(next_action)
                next_action["farmer"] = _physical

        # ---- Update tracking state
        self._last_step = state.step
        self._last_money = state.me.money

        return next_action
