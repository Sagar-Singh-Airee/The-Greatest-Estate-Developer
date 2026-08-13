
"""
V3 Future-State Action Transitions.

V3.3

This module applies hypothetical actions to a mutable
FutureState.

This is NOT the real game engine.

It is a planning approximation intended to answer:

    "What would the important economic state look like
     after this hypothetical action?"

Supported actions:

    PASS
    WATER
    PLANT
    HARVEST
    PLACE
    BUY_SEED
"""

from __future__ import annotations

from typing import Any

from estate_developer.planning.future_state import (
    FutureState,
    clone,
)


CANDIDATE_CROPS = (
    "WHEAT",
    "CARROT",
    "MELON",
)


# ============================================================
# PUBLIC API
# ============================================================

def apply_action(
    state: FutureState,
    action: list[Any] | tuple[Any, ...],
) -> FutureState:
    """
    Apply exactly ONE real game step.

    Movement-aware behavior:

        BUY_SEED
            immediate market action

        WATER / PLANT / HARVEST
            move one tile toward target when necessary

        PLACE
            move one tile toward nearest shed tile when necessary

    The input state is never modified.
    """

    next_state = clone(
        state
    )

    if not action:
        action_name = "PASS"

    else:
        action_name = str(
            action[0]
        ).upper()

    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    if action_name == "PASS":

        _advance_time(
            next_state
        )

        return next_state

    # --------------------------------------------------------
    # BUY_SEED
    #
    # Market action. No farmer movement required.
    # --------------------------------------------------------

    if action_name == "BUY_SEED":

        _apply_buy_seed(
            next_state,
            action,
        )

        _advance_time(
            next_state
        )

        return next_state

    # --------------------------------------------------------
    # Determine target.
    # --------------------------------------------------------

    if action_name == "PLACE":

        target = _nearest_shed_tile(
            next_state.me.farmer.x,
            next_state.me.farmer.y,
        )

    else:

        target = _target_from_action(
            action
        )

    # --------------------------------------------------------
    # Targeted farmer actions require movement.
    # --------------------------------------------------------

    if target is None:

        _advance_time(
            next_state
        )

        return next_state

    current_x = (
        next_state.me.farmer.x
    )

    current_y = (
        next_state.me.farmer.y
    )

    target_x, target_y = target

    if (
        current_x != target_x
        or current_y != target_y
    ):

        _move_one_step(
            next_state,
            target_x,
            target_y,
        )

        _advance_time(
            next_state
        )

        return next_state

    # --------------------------------------------------------
    # Already standing on target.
    # Execute operation.
    # --------------------------------------------------------

    if action_name == "WATER":

        _apply_water(
            next_state,
            action,
        )

    elif action_name == "PLANT":

        _apply_plant(
            next_state,
            action,
        )

    elif action_name == "HARVEST":

        _apply_harvest(
            next_state,
            action,
        )

    elif action_name == "PLACE":

        _apply_place(
            next_state,
            action,
        )

    else:

        raise ValueError(
            f"Unsupported planning action: {action!r}"
        )

    _advance_time(
        next_state
    )

    return next_state


# ============================================================
# MOVEMENT
# ============================================================

SHED_TILES = (
    (4, 4),
    (5, 4),
    (4, 5),
    (5, 5),
)


def _nearest_shed_tile(
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


def _move_one_step(
    state: FutureState,
    tx: int,
    ty: int,
) -> None:
    """
    Reproduce the V2 scheduler's movement rule.

    The real scheduler uses:

        x < tx -> EAST
        x > tx -> WEST
        y < ty -> SOUTH
        y > ty -> NORTH

    Only one cardinal movement is performed per step.
    """

    x = state.me.farmer.x
    y = state.me.farmer.y

    if x < tx:

        x += 1

    elif x > tx:

        x -= 1

    elif y < ty:

        y += 1

    elif y > ty:

        y -= 1

    state.me.farmer.x = x
    state.me.farmer.y = y


# ============================================================
# TIME
# ============================================================

def _advance_time(
    state: FutureState,
) -> None:
    """
    Advance one simulation step.

    Kaggriculture uses 24 hours per day.
    """

    state.step += 1

    state.hour += 1

    if state.hour >= 24:

        state.hour = 0
        state.day += 1

    # Overage time is planning metadata, not an economic
    # quantity. Keep it non-negative.
    state.remaining_overage_time = max(
        0,
        state.remaining_overage_time,
    )


# ============================================================
# WATER
# ============================================================

def _apply_water(
    state: FutureState,
    action,
) -> None:
    """
    Mark the target plant as watered today.
    """

    target = _target_from_action(
        action
    )

    if target is None:
        return

    x, y = target

    tile = _tile_at(
        state.me.tiles,
        x,
        y,
    )

    if not isinstance(
        tile,
        dict,
    ):
        return

    if tile.get(
        "kind"
    ) != "PLANT":
        return

    tile["watered_today"] = True

    tile["consecutive_unwatered"] = 0


# ============================================================
# PLANT
# ============================================================

def _apply_plant(
    state: FutureState,
    action,
) -> None:
    """
    Consume one seed and create a basic plant tile.

    Growth details are intentionally conservative at V3.3.
    """
    crop = _crop_from_action(
        action
    )

    target = _target_from_action(
        action
    )

    if crop is None or target is None:
        return

    seed_count = int(
        state.private.seeds.get(
            crop,
            0,
        )
    )

    if seed_count <= 0:
        return

    x, y = target

    tile = _tile_at(
        state.me.tiles,
        x,
        y,
    )

    if tile is not None:
        return

    state.private.seeds[
        crop
    ] = seed_count - 1

    growth_days, max_yield = _crop_timing(
        crop
    )

    state.me.tiles[y][x] = {
        "kind": "PLANT",
        "crop": crop,
        "planted_day": state.day,
        "watered_today": False,
        "consecutive_unwatered": 0,
        "yield_units": 1,
        "max_lifespan_step": (
            state.step
            + (
                growth_days
                * 24
            )
        ),
        "fertilized_until_day": -1,
        "expected_max_yield": max_yield,
    }


# ============================================================
# HARVEST
# ============================================================

def _apply_harvest(
    state: FutureState,
    action,
) -> None:
    """
    Convert the active plant into farmer inventory.

    V3.3 uses the current tile yield_units as the harvested
    quantity.
    """

    target = _target_from_action(
        action
    )

    if target is None:
        return

    x, y = target

    tile = _tile_at(
        state.me.tiles,
        x,
        y,
    )

    if not isinstance(
        tile,
        dict,
    ):
        return

    if tile.get(
        "kind"
    ) != "PLANT":
        return

    crop = tile.get(
        "crop"
    )

    if crop is None:
        return

    quantity = max(
        1,
        int(
            tile.get(
                "yield_units",
                1,
            )
        ),
    )

    if not state.private.inventories:

        state.private.inventories.append(
            {}
        )

    inventory = state.private.inventories[
        0
    ]

    inventory[crop] = (
        int(
            inventory.get(
                crop,
                0,
            )
        )
        + quantity
    )

    state.me.tiles[y][x] = None


# ============================================================
# PLACE
# ============================================================

def _apply_place(
    state: FutureState,
    action,
) -> None:
    """
    Move the requested farmer inventory quantity into the shed.
    """

    crop = _crop_from_action(
        action
    )

    if crop is None:
        return

    quantity = 1

    if len(action) >= 3:

        try:
            quantity = max(
                1,
                int(
                    action[2]
                ),
            )

        except (
            TypeError,
            ValueError,
        ):
            quantity = 1

    if not state.private.inventories:
        return

    inventory = state.private.inventories[
        0
    ]

    available = int(
        inventory.get(
            crop,
            0,
        )
    )

    moved = min(
        available,
        quantity,
    )

    if moved <= 0:
        return

    inventory[crop] = (
        available - moved
    )

    state.private.shed[crop] = (
        int(
            state.private.shed.get(
                crop,
                0,
            )
        )
        + moved
    )


# ============================================================
# BUY SEED
# ============================================================

def _apply_buy_seed(
    state: FutureState,
    action,
) -> None:
    """
    Purchase one or more seeds at the current market-derived
    seed cost.

    V3.3 uses the existing economic crop profiles.
    """

    crop = _crop_from_action(
        action
    )

    if crop is None:
        return

    quantity = 1

    if len(action) >= 3:

        try:
            quantity = max(
                1,
                int(
                    action[2]
                ),
            )

        except (
            TypeError,
            ValueError,
        ):
            quantity = 1

    try:

        from estate_developer.economics.crops import (
            CROP_PROFILES,
        )

        profile = CROP_PROFILES[crop]

        total_cost = (
            float(
                profile.seed_cost
            )
            * quantity
        )

    except Exception:

        return

    if state.me.money < total_cost:
        return

    state.me.money -= total_cost

    state.private.seeds[crop] = (
        int(
            state.private.seeds.get(
                crop,
                0,
            )
        )
        + quantity
    )


# ============================================================
# HELPERS
# ============================================================

def _crop_from_action(
    action,
) -> str | None:

    if len(action) < 2:
        return None

    crop = action[1]

    if crop is None:
        return None

    return str(
        crop
    ).upper()


def _target_from_action(
    action,
):
    """
    Extract (x, y) from a hypothetical action.

    Supported shape:

        [ACTION, CROP, (x, y), ...]
    """

    if len(action) < 3:
        return None

    target = action[2]

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


def _tile_at(
    tiles,
    x: int,
    y: int,
):
    if y < 0 or y >= len(tiles):
        return None

    if x < 0 or x >= len(tiles[y]):
        return None

    return tiles[y][x]


def _crop_timing(
    crop: str,
) -> tuple[int, int]:
    # Return the repository-defined crop timing data.
    from estate_developer.economics.crops import (
        CROP_PROFILES,
    )

    profile = CROP_PROFILES.get(
        crop
    )

    if profile is None:
        raise ValueError(
            f"Unknown crop: {crop}"
        )

    return (
        int(
            profile.max_yield_day
        ),
        int(
            profile.max_yield_unfertilized
        ),
    )
