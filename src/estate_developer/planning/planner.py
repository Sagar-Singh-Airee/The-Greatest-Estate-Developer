
"""
V3 Short-Horizon Planner.

V3.9

This layer sits above the existing V2 task generator.

It does NOT replace the V2 scheduler yet.

Pipeline:

    V2 Generator
        ↓
    FarmTask candidates
        ↓
    V3 task -> hypothetical action
        ↓
    FutureState transition
        ↓
    projected value
        ↓
    rank candidates

The V2 task priority remains the deterministic tie-breaker.
"""

from __future__ import annotations

from typing import Any

from estate_developer.planning.future_state import (
    snapshot,
)

from estate_developer.planning.task_actions import (
    task_to_action,
    task_label,
)

from estate_developer.planning.transition import (
    apply_action,
)

from estate_developer.planning.rollout import (
    evaluate_state,
)

from estate_developer.planning.future_tasks import (
    generate_future_actions,
)




class ShortHorizonPlanner:

    # Keep search bounded.
    DEFAULT_BEAM_WIDTH = 4

    def __init__(
        self,
        *,
        horizon: int = 2,
        beam_width: int = DEFAULT_BEAM_WIDTH,
    ) -> None:

        if horizon < 1:
            raise ValueError(
                "horizon must be >= 1"
            )

        if beam_width < 1:
            raise ValueError(
                "beam_width must be >= 1"
            )

        self.horizon = int(
            horizon
        )

        self.beam_width = int(
            beam_width
        )

        # Cache is reset for every rank_tasks() call.
        self._memo = {}

    # ========================================================
    # SAFETY
    # ========================================================

    @staticmethod
    def _has_urgent_water(
        state,
        tasks,
    ) -> bool:

        for task in tasks:

            if task.task_type.value != "WATER":
                continue

            target = task.target

            if target is None:
                continue

            x, y = target

            if y < 0 or y >= len(state.me.tiles):
                continue

            if x < 0 or x >= len(state.me.tiles[y]):
                continue

            tile = state.me.tiles[y][x]

            if not isinstance(
                tile,
                dict,
            ):
                continue

            if int(
                tile.get(
                    "consecutive_unwatered",
                    0,
                )
            ) >= 1:

                return True

        return False

    # ========================================================
    # FIRST-TASK RANKING
    # ========================================================

    def rank_tasks(
        self,
        state,
        tasks,
    ) -> list[dict[str, Any]]:

        if not tasks:
            return []

        # Each planning decision gets a fresh transposition
        # table. Never reuse search results across real steps.
        self._memo.clear()

        results = []

        for first_task in tasks:

            first_action = task_to_action(
                first_task
            )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Safety is enforced inside the recursive search.
            # We do NOT filter BUY_SEED/PLANT here based on the
            # root state.
            # ------------------------------------------------

            first_state = apply_action(
                snapshot(
                    state
                ),
                first_action,
            )

            value, sequence = self._search(
                first_state,
                depth_remaining=max(
                    0,
                    self.horizon - 1,
                ),
            )

            results.append(
                {
                    "task": first_task,
                    "action": first_action,
                    "second_action": (
                        sequence[0]
                        if sequence
                        else None
                    ),
                    "sequence": sequence,
                    "projected_value": float(
                        value
                    ),
                    "priority": int(
                        first_task.priority
                    ),
                }
            )

        results.sort(
            key=lambda item: (
                item["projected_value"],
                item["priority"],
            ),
            reverse=True,
        )

        return results


    # ========================================================
    # STATE SIGNATURE
    # ========================================================

    @staticmethod
    def _state_signature(
        state,
    ):
        """
        Build a stable hashable signature for planning.

        Only state that can affect current V3 transitions or
        valuation is included.
        """

        farms = []

        for farm in state.farms:

            farms.append(
                (
                    round(
                        float(farm.money),
                        6,
                    ),
                    (
                        int(farm.farmer.x),
                        int(farm.farmer.y),
                    ),
                    tuple(
                        tuple(
                            (
                                (
                                    tile.get("kind"),
                                    tile.get("crop"),
                                    tile.get(
                                        "yield_units"
                                    ),
                                    tile.get(
                                        "watered_today"
                                    ),
                                    tile.get(
                                        "consecutive_unwatered"
                                    ),
                                    tile.get(
                                        "max_lifespan_step"
                                    ),
                                    tile.get(
                                        "planted_day"
                                    ),
                                )
                                if isinstance(
                                    tile,
                                    dict,
                                )
                                else tile
                            )
                            for tile in row
                        )
                        for row in farm.tiles
                    ),
                )
            )

        private = (
            tuple(
                sorted(
                    state.private.shed.items()
                )
            ),
            tuple(
                sorted(
                    state.private.seeds.items()
                )
            ),
            tuple(
                tuple(
                    sorted(
                        inventory.items()
                    )
                )
                for inventory
                in state.private.inventories
            ),
        )

        market = (
            tuple(
                sorted(
                    state.market.inventory.items()
                )
            ),
            tuple(
                sorted(
                    state.market.prices.items()
                )
            ),
        )

        return (
            int(state.step),
            int(state.day),
            int(state.hour),
            tuple(farms),
            private,
            market,
        )

    # ========================================================
    # RECURSIVE SEARCH
    # ========================================================

    def _search(
        self,
        state,
        depth_remaining: int,
    ):
        """
        Return:

            (best_value, best_sequence)

        `best_sequence` does not include the action that
        produced `state`; it contains only future actions.
        """

        # ----------------------------------------------------
        # Transposition lookup.
        # ----------------------------------------------------

        signature = self._state_signature(
            state
        )

        cache_key = (
            signature,
            int(depth_remaining),
        )

        cached = self._memo.get(
            cache_key
        )

        if cached is not None:

            return cached

        if depth_remaining <= 0:

            result = (
                evaluate_state(
                    state
                ),
                [],
            )

            self._memo[
                cache_key
            ] = result

            return result

        candidates = generate_future_actions(
            state
        )

        if not candidates:

            return (
                evaluate_state(
                    state
                ),
                [],
            )

        # ----------------------------------------------------
        # State-aware safety filtering.
        #
        # If an urgent watering condition exists NOW, do not
        # spend this simulated step on pure economic expansion.
        #
        # Once WATER resolves the urgent condition, the next
        # recursive state is free to consider BUY_SEED/PLANT.
        # ----------------------------------------------------

        urgent_water = False

        for row in state.me.tiles:

            for tile in row:

                if not isinstance(
                    tile,
                    dict,
                ):
                    continue

                if tile.get(
                    "kind"
                ) != "PLANT":
                    continue

                if int(
                    tile.get(
                        "consecutive_unwatered",
                        0,
                    )
                ) >= 1:

                    urgent_water = True
                    break

            if urgent_water:
                break

        if urgent_water:

            safe_candidates = []

            for action in candidates:

                action_type = (
                    str(
                        action[0]
                    ).upper()
                    if action
                    else "PASS"
                )

                if action_type in (
                    "BUY_SEED",
                    "PLANT",
                ):

                    continue

                safe_candidates.append(
                    action
                )

            if safe_candidates:

                candidates = safe_candidates

        # ----------------------------------------------------
        # Beam pruning.
        #
        # First estimate each action with one transition, then
        # keep only the strongest few branches.
        # ----------------------------------------------------

        scored = []

        for action in candidates:

            branch = apply_action(
                state,
                action,
            )

            estimate = evaluate_state(
                branch
            )

            scored.append(
                (
                    estimate,
                    action,
                    branch,
                )
            )

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        scored = scored[
            : self.beam_width
        ]

        best_value = float(
            "-inf"
        )

        best_sequence = []

        for _, action, branch in scored:

            future_value, future_sequence = (
                self._search(
                    branch,
                    depth_remaining - 1,
                )
            )

            if future_value > best_value:

                best_value = future_value

                best_sequence = [
                    action,
                    *future_sequence,
                ]

        result = (
            best_value,
            best_sequence,
        )

        self._memo[
            cache_key
        ] = result

        return result

    # ========================================================
    # CHOOSE
    # ========================================================

    def choose(
        self,
        state,
        tasks,
    ):

        ranked = self.rank_tasks(
            state,
            tasks,
        )

        if not ranked:
            return None

        return ranked[0]
