from __future__ import annotations

from typing import Any
from estate_developer.state.parser import ObservationState
from estate_developer.planning.generator import TaskGenerator
from estate_developer.planning.scheduler import TaskScheduler
from estate_developer.execution.hand_assignment import HandAssignmentSolver
from estate_developer.simulation.state_copy import copy_observation
from estate_developer.simulation.transition import apply_action, tick_environment
from estate_developer.strategic.terminal_value import TerminalValueCalculator


class BeamSearchPlanner:
    """
    V9 True Rollout Beam Search.

    At each depth step the simulator advances the state forward,
    so the agent can reason about what the board looks like in
    future turns — not just the current one.
    """

    def __init__(self, beam_width: int = 3, max_depth: int = 3):
        self.beam_width = beam_width
        self.max_depth = max_depth
        self.generator = TaskGenerator()
        self.scheduler = TaskScheduler()
        self.hand_solver = HandAssignmentSolver()
        self.terminal_value = TerminalValueCalculator()

    # ============================================================
    # ACTION CANDIDATE GENERATION
    # ============================================================

    def generate_candidate_actions(
        self, state: ObservationState,
        opponent_model=None,
    ) -> list[dict[str, Any]]:
        """
        Generate sensible candidate actions for a single turn.
        Returns up to `beam_width` distinct action dicts.

        KEY FIX: Market orders are now determined by MarketManager
        directly here, so the action we SCORE is exactly the action
        we EXECUTE. No post-search mutation.
        """
        from estate_developer.planning.tasks import TaskType
        from estate_developer.economics.market_manager import MarketManager

        market_manager = MarketManager()
        tasks = self.generator.generate(state)

        if not tasks:
            from estate_developer.planning.tasks import FarmTask
            tasks = [FarmTask(task_type=TaskType.PASS, priority=0)]

        # Widen the search window: consider up to beam_width*2 tasks,
        # not just the top 3. This prevents strategic actions buried
        # in the queue from being permanently ignored.
        top_tasks = tasks[: max(self.beam_width * 2, 6)]

        # Authoritative market sell orders for THIS state
        sell_orders = market_manager.get_optimal_sell_orders(
            state, opponent_model=opponent_model
        )

        candidates: list[dict[str, Any]] = []
        for selected_task in top_tasks:
            farmer_action = self.scheduler.farmer_action(
                selected_task, state,
            )

            # Build market orders for this candidate.
            # Start from the authoritative sell decisions.
            market_orders: list[list[Any]] = list(sell_orders)

            tt = selected_task.task_type
            if tt == TaskType.BUY_SEED and selected_task.crop:
                market_orders.append(
                    ["BUY_SEED", selected_task.crop, max(1, selected_task.quantity)]
                )
            elif tt == TaskType.BUY_ANIMAL and selected_task.crop:
                market_orders.append(
                    ["BUY_ANIMAL", selected_task.crop, max(1, selected_task.quantity)]
                )
            elif tt == TaskType.HIRE:
                market_orders.append(["HIRE"])
            elif tt == TaskType.BUY_LAND:
                market_orders.append(["BUY_LAND"])

            remaining_tasks = [
                t for t in tasks if t is not selected_task
            ]
            hand_actions = self.hand_solver.assign(
                state, remaining_tasks,
            )

            candidates.append({
                "farmer": farmer_action,
                "hands": hand_actions,
                "market": market_orders[:10],
            })

        # Deduplicate
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for cand in candidates:
            rep = str(cand)
            if rep not in seen:
                seen.add(rep)
                unique.append(cand)

        return unique[:self.beam_width]

    # ============================================================
    # FORWARD SIMULATE A SINGLE ACTION
    # ============================================================

    @staticmethod
    def _apply_and_advance(
        state: ObservationState,
        action: dict[str, Any],
    ) -> ObservationState:
        """
        Deep-copy `state`, apply `action`, tick environment,
        and return the resulting state.
        """
        next_state = copy_observation(state)
        apply_action(next_state, action)
        tick_environment(next_state)
        return next_state

    # ============================================================
    # TRUE ROLLOUT BEAM SEARCH
    # ============================================================

    def plan(
        self, initial_state: ObservationState, timeout: float = 1.8
    ) -> list[dict[str, Any]]:
        """
        Run a real forward-simulating beam search with a strict time limit.

        Each beam entry is (score, state, action_sequence).
        At every depth:
          1. Expand each entry by generating candidates from *its* state.
          2. Apply each candidate through the simulator → next_state.
          3. Score next_state via TerminalValueCalculator.
          4. Keep the top `beam_width` entries.

        Returns the best action sequence found.
        """
        import time
        start_time = time.time()
        
        BeamEntry = tuple[float, ObservationState, list[dict[str, Any]]]

        initial_score = self.terminal_value.calculate(initial_state)
        beam: list[BeamEntry] = [
            (initial_score, initial_state, []),
        ]
        
        best_overall = beam[0]

        for _depth in range(self.max_depth):
            expansions: list[BeamEntry] = []

            for _score, current_state, seq in beam:
                # Check timeout before expanding
                if time.time() - start_time > timeout:
                    break
                    
                candidates = self.generate_candidate_actions(
                    current_state,
                )

                for action in candidates:
                    next_state = self._apply_and_advance(
                        current_state, action,
                    )
                    next_score = self.terminal_value.calculate(
                        next_state,
                    )
                    exp_entry = (next_score, next_state, seq + [action])
                    expansions.append(exp_entry)
                    
                    if next_score > best_overall[0]:
                        best_overall = exp_entry

            if not expansions or time.time() - start_time > timeout:
                break

            # Keep best beam_width entries
            expansions.sort(key=lambda e: e[0], reverse=True)
            beam = expansions[: self.beam_width]

        best_seq = best_overall[2]
        return best_seq if best_seq else [
            {"farmer": ["PASS"], "hands": [], "market": []}
        ]
