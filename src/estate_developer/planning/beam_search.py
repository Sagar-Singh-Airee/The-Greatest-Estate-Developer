from __future__ import annotations

from typing import Any

from estate_developer.state.parser import (
    ObservationState,
)

from estate_developer.planning.generator import (
    TaskGenerator,
)

from estate_developer.planning.scheduler import (
    TaskScheduler,
)

from estate_developer.execution.hand_assignment import (
    HandAssignmentSolver,
)

from estate_developer.strategic.terminal_value import (
    TerminalValueCalculator,
)

from estate_developer.simulation.simulator import (
    Simulator,
)


class BeamSearchPlanner:
    """
    V11-backed rollout Beam Search.

    Candidate generation and scoring remain unchanged.
    Forward simulation now goes exclusively through the
    certified V11-backed Simulator.
    """

    def __init__(
        self,
        beam_width: int = 3,
        max_depth: int = 1,
    ):
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
        self,
        state: ObservationState,
        opponent_model=None,
    ) -> list[dict[str, Any]]:
        """
        Generate sensible candidate actions for a single turn.

        Market orders are constructed here and the exact resulting
        candidate is what gets scored by the rollout.
        """

        from estate_developer.planning.tasks import (
            TaskType,
        )

        from estate_developer.economics.market_manager import (
            MarketManager,
        )

        market_manager = MarketManager()

        tasks = self.generator.generate(
            state
        )

        if not tasks:

            from estate_developer.planning.tasks import (
                FarmTask,
            )

            tasks = [
                FarmTask(
                    task_type=TaskType.PASS,
                    priority=0,
                )
            ]

        # Widen search window.
        top_tasks = tasks[
            : max(
                self.beam_width * 2,
                6,
            )
        ]

        # Authoritative market sell orders for this state.
        sell_orders = (
            market_manager.get_optimal_sell_orders(
                state,
                opponent_model=opponent_model,
            )
        )

        candidates: list[
            dict[str, Any]
        ] = []

        for selected_task in top_tasks:

            farmer_action = (
                self.scheduler.farmer_action(
                    selected_task,
                    state,
                )
            )

            market_orders: list[
                list[Any]
            ] = list(
                sell_orders
            )

            tt = selected_task.task_type

            if (
                tt == TaskType.BUY_SEED
                and selected_task.crop
            ):

                market_orders.append(
                    [
                        "BUY_SEED",
                        selected_task.crop,
                        max(
                            1,
                            selected_task.quantity,
                        ),
                    ]
                )

            elif (
                tt == TaskType.BUY_ANIMAL
                and selected_task.crop
            ):

                market_orders.append(
                    [
                        "BUY_ANIMAL",
                        selected_task.crop,
                        max(
                            1,
                            selected_task.quantity,
                        ),
                    ]
                )

            elif tt == TaskType.HIRE:

                market_orders.append(
                    ["HIRE"]
                )

            elif tt == TaskType.BUY_LAND:

                market_orders.append(
                    ["BUY_LAND"]
                )

            remaining_tasks = [
                task
                for task in tasks
                if task is not selected_task
            ]

            hand_actions = (
                self.hand_solver.assign(
                    state,
                    remaining_tasks,
                )
            )

            candidates.append(
                {
                    "farmer": farmer_action,
                    "hands": hand_actions,
                    "market": market_orders[:10],
                }
            )

        # Deduplicate.
        unique: list[
            dict[str, Any]
        ] = []

        seen: set[str] = set()

        for candidate in candidates:

            representation = str(
                candidate
            )

            if representation in seen:
                continue

            seen.add(
                representation
            )

            unique.append(
                candidate
            )

        return unique[
            : self.beam_width
        ]

    # ============================================================
    # V11 FORWARD SIMULATION
    # ============================================================

    @staticmethod
    def _apply_and_advance(
        state: ObservationState,
        action: dict[str, Any],
    ) -> ObservationState:
        """
        Run exactly one V11 transition.

        The Simulator performs a defensive state copy and then
        delegates to the certified V11 step_state() engine.
        """

        simulator = Simulator(
            state
        )

        return simulator.step(
            action
        )

    # ============================================================
    # TRUE ROLLOUT BEAM SEARCH
    # ============================================================

    def plan(
        self,
        initial_state: ObservationState,
        timeout: float = 1.8,
    ) -> list[dict[str, Any]]:
        """
        Run forward-simulating Beam Search.

        Each beam entry is:

            (score, state, action_sequence)

        At every depth:

            1. Generate candidates from the current state.
            2. Advance through V11.
            3. Score the resulting state.
            4. Keep the best beam_width entries.

        Returns the best action sequence found.
        """

        import time

        start_time = time.time()

        BeamEntry = tuple[
            float,
            ObservationState,
            list[dict[str, Any]],
        ]

        initial_score = (
            self.terminal_value.calculate(
                initial_state
            )
        )

        beam: list[
            BeamEntry
        ] = [
            (
                initial_score,
                initial_state,
                [],
            )
        ]

        best_overall = beam[0]

        for _depth in range(
            self.max_depth
        ):

            expansions: list[
                BeamEntry
            ] = []

            for (
                _score,
                current_state,
                sequence,
            ) in beam:

                if (
                    time.time()
                    - start_time
                    > timeout
                ):
                    break

                candidates = (
                    self.generate_candidate_actions(
                        current_state
                    )
                )

                for action in candidates:

                    next_state = (
                        self._apply_and_advance(
                            current_state,
                            action,
                        )
                    )

                    next_score = (
                        self.terminal_value.calculate(
                            next_state
                        )
                    )

                    expanded_entry = (
                        next_score,
                        next_state,
                        sequence + [action],
                    )

                    expansions.append(
                        expanded_entry
                    )

                    if (
                        not best_overall[2]
                        or next_score
                        > best_overall[0]
                    ):
                        best_overall = (
                            expanded_entry
                        )

            if (
                not expansions
                or (
                    time.time()
                    - start_time
                    > timeout
                )
            ):
                break

            expansions.sort(
                key=lambda entry: entry[0],
                reverse=True,
            )

            # Once valid expansions exist, the best expansion
            # is the best trajectory candidate for this depth.
            # Never return the synthetic empty initial sequence.
            best_overall = expansions[0]

            beam = expansions[
                : self.beam_width
            ]

        best_sequence = (
            best_overall[2]
        )

        return (
            best_sequence
            if best_sequence
            else [
                {
                    "farmer": ["PASS"],
                    "hands": [],
                    "market": [],
                }
            ]
        )
