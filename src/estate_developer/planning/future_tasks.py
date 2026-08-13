
"""
V3 Future Task Generation.

Creates a small set of plausible follow-up actions from a
FutureState.

This is intentionally separate from the V2 TaskGenerator.

V3.10 supports:

    HARVEST
    WATER
    PLANT
    PLACE
    BUY_SEED
    PASS
"""

from __future__ import annotations

from estate_developer.planning.future_state import (
    FutureState,
)


CANDIDATE_CROPS = (
    "WHEAT",
    "CARROT",
    "MELON",
)


def generate_future_actions(
    state: FutureState,
) -> list[list]:
    """
    Produce plausible next hypothetical actions.
    """

    actions = []

    # --------------------------------------------------------
    # Always allow PASS.
    # --------------------------------------------------------

    actions.append(
        ["PASS"]
    )

    # --------------------------------------------------------
    # Active crop actions.
    # --------------------------------------------------------

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

            # Harvest-ready.
            lifespan = tile.get(
                "max_lifespan_step"
            )

            if (
                lifespan is not None
                and state.step
                >= int(lifespan)
            ):

                actions.append(
                    [
                        "HARVEST",
                        crop,
                        (x, y),
                    ]
                )

            # Water if not already watered.
            if not tile.get(
                "watered_today",
                False,
            ):

                actions.append(
                    [
                        "WATER",
                        crop,
                        (x, y),
                    ]
                )

    # --------------------------------------------------------
    # Farmer inventory -> shed.
    # --------------------------------------------------------

    if state.private.inventories:

        inventory = (
            state.private.inventories[0]
        )

        for crop in CANDIDATE_CROPS:

            quantity = int(
                inventory.get(
                    crop,
                    0,
                )
            )

            if quantity > 0:

                actions.append(
                    [
                        "PLACE",
                        crop,
                        quantity,
                    ]
                )

                break

    # --------------------------------------------------------
    # Empty production tile -> PLANT.
    # --------------------------------------------------------

    empty_target = None

    for y, row in enumerate(
        state.me.tiles
    ):

        for x, tile in enumerate(row):

            if tile is None:

                empty_target = (
                    x,
                    y,
                )

                break

        if empty_target is not None:
            break

    if empty_target is not None:

        for crop in CANDIDATE_CROPS:

            if int(
                state.private.seeds.get(
                    crop,
                    0,
                )
            ) > 0:

                actions.append(
                    [
                        "PLANT",
                        crop,
                        empty_target,
                    ]
                )

    # --------------------------------------------------------
    # BUY_SEED if affordable.
    # --------------------------------------------------------

    try:

        from estate_developer.economics.crops import (
            CROP_PROFILES,
        )

        for crop in CANDIDATE_CROPS:

            seed_count = int(
                state.private.seeds.get(
                    crop,
                    0,
                )
            )

            if seed_count > 0:
                continue

            profile = CROP_PROFILES.get(
                crop
            )

            if profile is None:
                continue

            if (
                state.me.money
                >= profile.seed_cost
            ):

                actions.append(
                    [
                        "BUY_SEED",
                        crop,
                        1,
                    ]
                )

    except Exception:
        pass

    return actions
