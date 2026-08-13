
"""
V3 execution sequence utilities.

Converts a high-level planning intent into the exact sequence
of one-step farmer actions required by the V2 movement model.
"""

from __future__ import annotations

from typing import Any

from estate_developer.planning.future_state import (
    FutureState,
)


SHED_TILES = (
    (4, 4),
    (5, 4),
    (4, 5),
    (5, 5),
)


def nearest_shed_tile(
    x: int,
    y: int,
) -> tuple[int, int]:

    return min(
        SHED_TILES,
        key=lambda pos: (
            abs(x - pos[0])
            + abs(y - pos[1])
        ),
    )


def movement_step(
    x: int,
    y: int,
    tx: int,
    ty: int,
) -> str:

    if x < tx:
        return "EAST"

    if x > tx:
        return "WEST"

    if y < ty:
        return "SOUTH"

    if y > ty:
        return "NORTH"

    return "PASS"


def intent_target(
    state: FutureState,
    intent: list[Any],
):
    """
    Return the movement target for a high-level intent.

    BUY_SEED and PASS have no movement target.
    """

    if not intent:
        return None

    action = str(
        intent[0]
    ).upper()

    if action in (
        "BUY_SEED",
        "PASS",
    ):
        return None

    if action == "PLACE":

        return nearest_shed_tile(
            state.me.farmer.x,
            state.me.farmer.y,
        )

    if len(intent) < 3:
        return None

    target = intent[2]

    if (
        not isinstance(
            target,
            (tuple, list),
        )
        or len(target) != 2
    ):
        return None

    return (
        int(target[0]),
        int(target[1]),
    )


def normalize_intent(
    state: FutureState,
    intent: list[Any],
) -> list[str]:
    """
    Return the exact immediate executable action.

    If movement is required, return one cardinal direction.

    If already at target, return the actual operation.
    """

    if not intent:
        return ["PASS"]

    action = str(
        intent[0]
    ).upper()

    if action == "BUY_SEED":
        return [
            "BUY_SEED"
        ]

    if action == "PASS":
        return [
            "PASS"
        ]

    target = intent_target(
        state,
        intent,
    )

    if target is None:
        return [
            "PASS"
        ]

    x = state.me.farmer.x
    y = state.me.farmer.y

    tx, ty = target

    if (
        x != tx
        or y != ty
    ):

        return [
            movement_step(
                x,
                y,
                tx,
                ty,
            )
        ]

    if action == "WATER":

        return [
            "WATER"
        ]

    if action == "PLANT":

        return [
            "PLANT"
        ]

    if action == "HARVEST":

        return [
            "HARVEST"
        ]

    if action == "PLACE":

        return [
            "PLACE"
        ]

    return [
        action
    ]
