
"""
V3 2-Step Rollout Evaluator.

This is the first true look-ahead component.

It does NOT modify the V2 agent.

The evaluator:

    1. Takes a current FutureState.
    2. Evaluates one candidate first action.
    3. Applies that action to a hypothetical state.
    4. Looks at the next set of candidate tasks.
    5. Applies the best second action.
    6. Scores the resulting hypothetical state.

V3.6 deliberately uses a short horizon of 2.
"""

from __future__ import annotations

from typing import Any

from estate_developer.planning.future_state import (
    FutureState,
    snapshot,
    clone,
)

from estate_developer.planning.transition import (
    apply_action,
)


def rollout_two_steps(
    state: FutureState,
    first_action: list[Any],
    second_action: list[Any] | None = None,
) -> FutureState:
    """
    Apply one or two hypothetical actions.

    The input state is never modified.
    """

    after_first = apply_action(
        state,
        first_action,
    )

    if second_action is None:
        return after_first

    return apply_action(
        after_first,
        second_action,
    )


def evaluate_state(
    state: FutureState,
) -> float:
    """
    Basic V3.6 projected-value function.

    This intentionally avoids pretending to reproduce the full
    Kaggriculture reward formula.

    It measures the economic state we can safely infer:

        money
        + shed inventory value
        + farmer inventory value
        + active production value
        - unresolved empty capacity

    This is a planning heuristic, not the game's official score.
    """

    score = float(
        state.me.money
    )

    prices = state.market.prices

    # --------------------------------------------------------
    # Shed value.
    # --------------------------------------------------------

    for crop, quantity in (
        state.private.shed.items()
    ):

        price = float(
            prices.get(
                crop,
                0,
            )
        )

        score += (
            int(quantity)
            * price
        )

    # --------------------------------------------------------
    # Farmer inventory value.
    # --------------------------------------------------------

    if state.private.inventories:

        inventory = (
            state.private.inventories[0]
        )

        for crop, quantity in inventory.items():

            price = float(
                prices.get(
                    crop,
                    0,
                )
            )

            score += (
                int(quantity)
                * price
            )

    # --------------------------------------------------------
    # Profile-driven active crop value.
    #
    # IMPORTANT:
    # max_lifespan_step is used for expiry/survival logic,
    # not as the crop's first-production timer.
    #
    # CropProfile.first_yield_day / max_yield_day define the
    # actual production cycle.
    # --------------------------------------------------------

    from estate_developer.economics.crops import (
        CROP_PROFILES,
    )

    for y, row in enumerate(
        state.me.tiles
    ):

        for x, tile in enumerate(row):

            if not isinstance(
                tile,
                dict,
            ):
                continue

            if tile.get(
                "kind"
            ) != "PLANT":
                continue

            crop = tile.get(
                "crop"
            )

            if crop is None:
                continue

            profile = CROP_PROFILES.get(
                crop
            )

            if profile is None:
                continue

            price = float(
                prices.get(
                    crop,
                    0,
                )
            )

            max_yield = float(
                profile.max_yield_unfertilized
            )

            # ------------------------------------------------
            # Convert crop-profile days to simulation steps.
            # ------------------------------------------------

            first_yield_steps = (
                int(
                    profile.first_yield_day
                )
                * 24
            )

            max_yield_steps = (
                int(
                    profile.max_yield_day
                )
                * 24
            )

            planted_day = int(
                tile.get(
                    "planted_day",
                    state.day,
                )
            )

            age_steps = (
                (
                    int(state.day)
                    - planted_day
                )
                * 24
                + int(state.hour)
            )

            # ------------------------------------------------
            # Production progress.
            #
            # Before first yield:
            #      zero realized standing value.
            #
            # Between first and max yield:
            #      increase gradually.
            #
            # At/after max yield:
            #      standing crop itself contributes zero because
            #      the economic action should be HARVEST.
            # ------------------------------------------------

            if age_steps < first_yield_steps:

                production_progress = 0.0

            elif (
                age_steps
                >= max_yield_steps
            ):

                production_progress = 0.0

            elif (
                max_yield_steps
                <= first_yield_steps
            ):

                production_progress = 0.0

            else:

                production_progress = (
                    (
                        age_steps
                        - first_yield_steps
                    )
                    /
                    (
                        max_yield_steps
                        - first_yield_steps
                    )
                )

                production_progress = min(
                    1.0,
                    max(
                        0.0,
                        production_progress,
                    ),
                )

            # ------------------------------------------------
            # Watering risk.
            #
            # Treat missed watering as an expected-yield
            # reduction, not a direct percentage of total
            # market value.
            # ------------------------------------------------

            unwatered = int(
                tile.get(
                    "consecutive_unwatered",
                    0,
                )
            )

            risk_factor = max(
                0.0,
                1.0
                - (
                    0.10
                    * unwatered
                ),
            )

            effective_yield = (
                max_yield
                * risk_factor
            )

            crop_value = (
                effective_yield
                * price
                * production_progress
            )

            score += crop_value

    return score


def compare_first_actions(
    state: FutureState,
    candidates: list[list[Any]],
    second_action_provider=None,
) -> list[tuple[float, list[Any]]]:
    """
    Evaluate multiple first-action candidates.

    `second_action_provider` may be supplied later by the
    V3 planner. For now it can return a single follow-up action
    for the simulated state.
    """

    results = []

    for first_action in candidates:

        after_first = apply_action(
            state,
            first_action,
        )

        second_action = None

        if second_action_provider is not None:

            second_action = (
                second_action_provider(
                    after_first
                )
            )

        final_state = after_first

        if second_action is not None:

            final_state = apply_action(
                after_first,
                second_action,
            )

        score = evaluate_state(
            final_state
        )

        results.append(
            (
                score,
                first_action,
            )
        )

    results.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return results
