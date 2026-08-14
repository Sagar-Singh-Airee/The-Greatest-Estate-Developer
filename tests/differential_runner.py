
"""
V11 Differential Harness

Runs the real Kaggriculture environment and our V11 simulator
with the exact same action sequence, then compares state.
"""

from __future__ import annotations

from typing import Any
import copy

from estate_developer.state.parser import (
    ObservationParser,
    ObservationState,
)
from estate_developer.simulation.simulation_context import (
    SimulationContext,
)
from estate_developer.simulation.v11_transition import (
    step_state,
)


def _normalize(value: Any) -> Any:
    """
    Convert Kaggle Struct / mapping-like objects into plain Python
    structures before differential comparison.
    """

    # Standard mappings.
    if isinstance(value, dict):
        return {
            key: _normalize(item)
            for key, item in value.items()
        }

    # Kaggle Struct objects are mapping-like. Avoid importing
    # kaggle_environments into the production simulator solely for
    # testing; structural conversion is enough here.
    if hasattr(value, "items"):
        try:
            return {
                key: _normalize(item)
                for key, item in value.items()
            }
        except Exception:
            pass

    # Lists / tuples.
    if isinstance(value, (list, tuple)):
        return [
            _normalize(item)
            for item in value
        ]

    return value



def _diff_dict(
    real: Any,
    simulated: Any,
    path: str = "",
) -> list[str]:
    """
    Recursive structural diff.

    Returns human-readable mismatch paths.
    """

    real = _normalize(real)
    simulated = _normalize(simulated)

    if type(real) is not type(simulated):
        return [
            f"{path}: type {type(real).__name__} "
            f"!= {type(simulated).__name__}"
        ]

    if isinstance(real, dict):

        mismatches: list[str] = []

        real_keys = set(real)
        sim_keys = set(simulated)

        for key in sorted(real_keys - sim_keys):
            mismatches.append(
                f"{path}.{key}: missing in simulated"
            )

        for key in sorted(sim_keys - real_keys):
            mismatches.append(
                f"{path}.{key}: unexpected in simulated"
            )

        for key in sorted(real_keys & sim_keys):
            child = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            mismatches.extend(
                _diff_dict(
                    real[key],
                    simulated[key],
                    child,
                )
            )

        return mismatches

    if isinstance(real, (list, tuple)):

        mismatches = []

        if len(real) != len(simulated):
            mismatches.append(
                f"{path}: length "
                f"{len(real)} != {len(simulated)}"
            )
            return mismatches

        for index, (a, b) in enumerate(
            zip(real, simulated)
        ):
            mismatches.extend(
                _diff_dict(
                    a,
                    b,
                    f"{path}[{index}]",
                )
            )

        return mismatches

    if real != simulated:
        return [
            f"{path}: {real!r} != {simulated!r}"
        ]

    return []


def observation_to_dict(
    state: ObservationState,
) -> dict[str, Any]:
    """
    Normalize ObservationState into a structure that can be
    compared recursively.
    """

    return {
        "step": state.step,
        "day": state.day,
        "hour": state.hour,
        "player": state.player,
        "remainingOverageTime":
            state.remaining_overage_time,
        "farms": [
            {
                "money": farm.money,
                "tiles": copy.deepcopy(farm.tiles),
                "farmer": [
                    farm.farmer.x,
                    farm.farmer.y,
                ],
                "hands": [
                    [p.x, p.y]
                    for p in farm.hands
                ],
                "unlocked_quadrants":
                    list(farm.unlocked_quadrants),
                "hires_today":
                    farm.hires_today,
            }
            for farm in state.farms
        ],
        "private": {
            "shed": copy.deepcopy(
                state.private.shed
            ),
            "seeds": copy.deepcopy(
                state.private.seeds
            ),
            "inventories": [
                copy.deepcopy(inv)
                for inv in state.private.inventories
            ],
        },
        "market": {
            "inventory": copy.deepcopy(
                state.market.inventory
            ),
            "prices": copy.deepcopy(
                state.market.prices
            ),
        },
        "town": {
            "unlocked_shops":
                list(
                    state.town.unlocked_shops
                )
        },
    }


def compare_states(
    real_raw: dict[str, Any],
    simulated: ObservationState,
) -> list[str]:
    """
    Compare a raw Kaggriculture observation against V11.
    """

    real_state = ObservationParser.parse(
        real_raw
    )

    real_dict = observation_to_dict(
        real_state
    )

    sim_dict = observation_to_dict(
        simulated
    )

    return _diff_dict(
        real_dict,
        sim_dict,
    )


def replay_action_sequence(
    initial_raw: dict[str, Any],
    real_observations: dict[int, dict[str, Any]],
    actions_by_step: dict[int, dict[str, Any]],
    *,
    seed: int | None = None,
    compare_steps: list[int] | None = None,
) -> None:
    """
    Replay a recorded real-environment trajectory through V11.

    Raises AssertionError on the first mismatch.
    """

    initial_state = ObservationParser.parse(
        initial_raw
    )

    state = initial_state

    context = SimulationContext(
        seed=seed,
    )

    if compare_steps is None:
        compare_steps = sorted(
            real_observations
        )

    for current_step in sorted(
        actions_by_step
    ):

        action = actions_by_step[
            current_step
        ]

        state = step_state(
            state,
            action,
            context=context,
        )

        if state.step not in compare_steps:
            continue

        if state.step not in real_observations:
            raise AssertionError(
                f"No real observation for step "
                f"{state.step}"
            )

        mismatches = compare_states(
            real_observations[state.step],
            state,
        )

        if mismatches:

            preview = "\n".join(
                mismatches[:40]
            )

            raise AssertionError(
                "V11 differential mismatch at "
                f"step {state.step}:\n"
                f"{preview}"
            )

    return None
