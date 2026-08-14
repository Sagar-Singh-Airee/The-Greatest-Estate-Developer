
"""
V11 Kaggriculture reference-faithful transition engine.

Phase currently implemented:
    - farmer/hand actions

Remaining phases:
    - market
    - town demand
    - plant decay
    - end-of-day refresh
    - complete step orchestration
"""

from __future__ import annotations

from typing import Any

from estate_developer.simulation.simulation_context import (
    SimulationContext,
)
from estate_developer.simulation.state_copy import (
    copy_observation,
)
from estate_developer.simulation.reference_rules import (
    ANIMALS,
    CROPS,
)
from estate_developer.state.parser import (
    ObservationState,
)


# ============================================================
# Local helpers — mirrors real Kaggriculture semantics
# ============================================================

def _farmer_position(
    farm: Any,
    unit_index: int,
) -> tuple[int, int] | None:
    """
    unit_index 0 = main farmer
    unit_index 1+ = hand index
    """

    if unit_index == 0:
        return (
            int(farm.farmer.x),
            int(farm.farmer.y),
        )

    hand_index = unit_index - 1

    if hand_index >= len(farm.hands):
        return None

    pos = farm.hands[hand_index]

    return (
        int(pos.x),
        int(pos.y),
    )


def _set_unit_position(
    farm: Any,
    unit_index: int,
    x: int,
    y: int,
) -> None:
    """
    Update the actor's position.

    Kaggriculture mutates the public farm position directly.
    """

    from estate_developer.state.parser import Position

    position = Position(
        x=int(x),
        y=int(y),
    )

    if unit_index == 0:
        object.__setattr__(
            farm,
            "farmer",
            position,
        )
        return

    hands = list(farm.hands)
    hand_index = unit_index - 1

    if hand_index < 0 or hand_index >= len(hands):
        return

    hands[hand_index] = position

    object.__setattr__(
        farm,
        "hands",
        tuple(hands),
    )


def _farmer_inventory(
    private: Any,
    unit_index: int,
) -> dict[str, int]:
    """
    Obtain the acting unit inventory.

    Mirrors Kaggriculture's convention:
        inventories[0] = farmer
        inventories[1:] = hands

    The internal state stores inventories as a tuple, so when a hand
    inventory does not exist yet we replace the tuple with an expanded one.
    """

    inventories = list(private.inventories)

    while len(inventories) <= unit_index:
        inventories.append({})

    if len(inventories) != len(private.inventories):
        object.__setattr__(
            private,
            "inventories",
            tuple(inventories),
        )

    return inventories[unit_index]


def _inv_add(
    inventory: dict[str, int],
    item: str,
    quantity: int = 1,
) -> None:

    if quantity <= 0:
        return

    inventory[item] = (
        inventory.get(item, 0)
        + quantity
    )


def _inv_take(
    inventory: dict[str, int],
    item: str,
    quantity: int = 1,
) -> bool:

    if quantity <= 0:
        return False

    if inventory.get(item, 0) < quantity:
        return False

    inventory[item] -= quantity

    if inventory[item] == 0:
        del inventory[item]

    return True


def _shed_access_tiles(
    board_size: int,
) -> tuple[tuple[int, int], ...]:

    half = board_size // 2

    return (
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    )


def _is_shed_adjacent(
    position: tuple[int, int],
    board_size: int,
) -> bool:

    return position in set(
        _shed_access_tiles(board_size)
    )


# ============================================================
# Unit action engine
# ============================================================

def apply_unit_action(
    state: ObservationState,
    action: list[Any],
    *,
    unit_index: int,
    context: SimulationContext,
) -> None:
    """
    Apply one farmer/hand action using real Kaggriculture semantics.

    Invalid / illegal actions are silent no-ops, matching the reference
    environment.

    The action operates on the acting unit's CURRENT TILE.
    """

    if not isinstance(action, list) or not action:
        return

    farm = state.me
    private = state.private

    position = _farmer_position(
        farm,
        unit_index,
    )

    if position is None:
        return

    fx, fy = position

    op = action[0]

    # --------------------------------------------------------
    # Movement
    # --------------------------------------------------------

    moves = {
        "NORTH": (0, -1),
        "SOUTH": (0, 1),
        "EAST": (1, 0),
        "WEST": (-1, 0),
    }

    if op in moves:

        dx, dy = moves[op]

        nx = fx + dx
        ny = fy + dy

        if not (
            0 <= nx < context.board_size
            and 0 <= ny < context.board_size
        ):
            return

        if farm.tiles[ny][nx] == "LOCKED":
            return

        _set_unit_position(
            farm,
            unit_index,
            nx,
            ny,
        )

        return

    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    if op == "PASS":
        return

    # --------------------------------------------------------
    # Current tile
    # --------------------------------------------------------

    tile = farm.tiles[fy][fx]

    if tile == "LOCKED":
        return

    # --------------------------------------------------------
    # PLANT
    # --------------------------------------------------------

    if op == "PICKUP":
        if not _is_shed_adjacent(
            (fx, fy),
            context.board_size,
        ):
            return

        if len(action) < 2:
            return

        item = str(action[1])

        n = (
            int(action[2])
            if len(action) >= 3
            else 1
        )

        if n <= 0:
            return

        inventory = _farmer_inventory(
            private,
            unit_index,
        )

        available = int(
            private.shed.get(
                item,
                0,
            )
        )

        n = min(
            n,
            available,
        )

        if n <= 0:
            return

        # Match Kaggriculture:
        # preserve the zero-valued shed key.
        private.shed[item] = (
            available - n
        )

        _inv_add(
            inventory,
            item,
            n,
        )

        return

    if op == "PLANT":

        if len(action) < 2:
            return

        crop = action[1]

        if crop not in CROPS:
            return

        # Real environment only permits planting on an empty tile.
        if tile is not None:
            return

        if private.seeds.get(crop, 0) <= 0:
            return

        private.seeds[crop] -= 1

        crop_data = CROPS[crop]

        state.me.tiles[fy][fx] = {
            "kind": "PLANT",
            "crop": crop,
            "planted_day": state.day,
            "watered_today": False,
            "consecutive_unwatered": 1,
            "yield_units": (
                0
                if bool(crop_data["ongoing"])
                else 1
            ),
            "max_lifespan_step": (
                -1
                if bool(crop_data["ongoing"])
                else (
                    state.day
                    + int(crop_data["max_yield_day"])
                    + 1
                ) * context.turns_per_day
            ),
            "fertilized_until_day": -1,
        }

        return

    # --------------------------------------------------------
    # WATER
    # --------------------------------------------------------

    if op == "WATER":

        if not (
            isinstance(tile, dict)
            and tile.get("kind") == "PLANT"
        ):
            return

        if tile.get("watered_today"):
            return

        tile["watered_today"] = True

        crop_data = CROPS[tile["crop"]]

        # Non-ongoing crops gain yield directly from qualifying
        # watering days.
        if not bool(crop_data["ongoing"]):

            age_days = (
                state.day
                - int(tile["planted_day"])
            )

            window_start = (
                int(crop_data["max_yield_day"])
                + 1
            ) // 2

            if (
                window_start
                <= age_days
                <= int(crop_data["max_yield_day"])
            ):

                bonus = (
                    2
                    if int(
                        tile.get(
                            "fertilized_until_day",
                            -1,
                        )
                    ) >= state.day
                    else 1
                )

                tile["yield_units"] = min(
                    int(crop_data["max_yield"]),
                    int(
                        tile.get(
                            "yield_units",
                            0,
                        )
                    ) + bonus,
                )

        return

    # --------------------------------------------------------
    # HARVEST
    # --------------------------------------------------------

    if op == "HARVEST":

        if not isinstance(tile, dict):
            return

        units = int(
            tile.get(
                "yield_units",
                0,
            )
        )

        if units <= 0:
            return

        if tile.get("kind") == "PLANT":

            crop = str(tile["crop"])
            crop_data = CROPS[crop]

            # Real Kaggriculture guards against immature ongoing crops.
            if (
                state.day
                - int(tile["planted_day"])
                < int(crop_data["first_yield_day"])
            ):
                if bool(crop_data["ongoing"]):
                    return

                return

            inventory = _farmer_inventory(
                private,
                unit_index,
            )

            _inv_add(
                inventory,
                crop,
                units,
            )

            tile["yield_units"] = 0

            # Non-ongoing crops are removed after harvest.
            if not bool(crop_data["ongoing"]):
                state.me.tiles[fy][fx] = None

            return

        # Animal harvesting is implemented here as well because it is
        # fundamentally a unit action on the current tile.
        if "animal" in tile:

            animal = tile.get("animal")

            if animal not in ANIMALS:
                return

            inventory = _farmer_inventory(
                private,
                unit_index,
            )

            product = str(
                ANIMALS[animal]["product"]
            )

            _inv_add(
                inventory,
                product,
                units,
            )

            tile["yield_units"] = 0

        return

    # --------------------------------------------------------
    # FERTILIZE
    # --------------------------------------------------------

    if op == "FERTILIZE":

        if not (
            isinstance(tile, dict)
            and tile.get("kind") == "PLANT"
        ):
            return

        inventory = _farmer_inventory(
            private,
            unit_index,
        )

        if not _inv_take(
            inventory,
            "FERTILIZER",
            1,
        ):
            return

        # Active for current day + next two days.
        tile["fertilized_until_day"] = max(
            int(
                tile.get(
                    "fertilized_until_day",
                    -1,
                )
            ),
            state.day + 2,
        )

        return

    # --------------------------------------------------------
    # DIG
    # --------------------------------------------------------

    if op == "DIG":

        if tile is None:
            return

        # Cannot dig an occupied animal.
        if (
            isinstance(tile, dict)
            and "animal" in tile
        ):
            return

        farm.tiles[fy][fx] = None
        return

    # --------------------------------------------------------
    # BUILD_COOP
    # --------------------------------------------------------

    if op == "BUILD_COOP":

        if tile is not None:
            return

        farm.tiles[fy][fx] = {
            "kind": "COOP",
        }

        return

    # --------------------------------------------------------
    # BUILD_PASTURE
    # --------------------------------------------------------

    if op == "BUILD_PASTURE":

        if tile is not None:
            return

        farm.tiles[fy][fx] = {
            "kind": "PASTURE",
        }

        return

    # --------------------------------------------------------
    # PLACE
    # --------------------------------------------------------

    if op == "PLACE":

        if len(action) < 2:
            return

        item = str(action[1])

        inventory = _farmer_inventory(
            private,
            unit_index,
        )

        # ----------------------------------------------------
        # Animal placement.
        #
        # IMPORTANT:
        # If the tile is NOT a matching structure, we MUST
        # fall through to the shed-drop behavior below.
        # ----------------------------------------------------

        if item in ANIMALS:

            animal_data = ANIMALS[item]

            if (
                isinstance(tile, dict)
                and tile.get("kind")
                == animal_data["structure"]
                and "animal" not in tile
            ):

                if not _inv_take(
                    inventory,
                    item,
                    1,
                ):
                    return

                farm.tiles[fy][fx] = {
                    "kind": animal_data["structure"],
                    "animal": item,
                    "placed_day": state.day,
                    "yield_units": 0,
                    "consecutive_unfed": 0,
                    "fed_today": False,
                    "cared_today": False,
                    "fertilizer_available": False,
                    "pending_care_bonus": 0,
                }

                return

        # ----------------------------------------------------
        # Shed drop fallback.
        # ----------------------------------------------------

        if not _is_shed_adjacent(
            (fx, fy),
            context.board_size,
        ):
            return

        if len(action) >= 3:
            try:
                quantity = int(action[2])
            except (
                TypeError,
                ValueError,
            ):
                return
        else:
            quantity = 1

        if quantity <= 0:
            return

        quantity = min(
            quantity,
            inventory.get(item, 0),
        )

        if quantity <= 0:
            return

        current = sum(
            int(value)
            for value in private.shed.values()
        )

        room = max(
            0,
            context.shed_capacity - current,
        )

        quantity = min(
            quantity,
            room,
        )

        if quantity <= 0:
            return

        if not _inv_take(
            inventory,
            item,
            quantity,
        ):
            return

        private.shed[item] = (
            private.shed.get(item, 0)
            + quantity
        )

        return


    # --------------------------------------------------------
    # FEED
    # --------------------------------------------------------

    if op == "FEED":

        if not (
            isinstance(tile, dict)
            and "animal" in tile
        ):
            return

        if tile.get("fed_today"):
            return

        inventory = _farmer_inventory(
            private,
            unit_index,
        )

        if not _inv_take(
            inventory,
            "WHEAT",
            1,
        ):
            return

        tile["fed_today"] = True

        return

    # --------------------------------------------------------
    # COLLECT_FERTILIZER
    # --------------------------------------------------------

    if op == "COLLECT_FERTILIZER":

        if not (
            isinstance(tile, dict)
            and "animal" in tile
        ):
            return

        if not tile.get(
            "fertilizer_available",
            False,
        ):
            return

        tile["fertilizer_available"] = False

        inventory = _farmer_inventory(
            private,
            unit_index,
        )

        _inv_add(
            inventory,
            "FERTILIZER",
            1,
        )

        return

    # --------------------------------------------------------
    # CARE
    # --------------------------------------------------------

    if op == "CARE":

        if not (
            isinstance(tile, dict)
            and "animal" in tile
        ):
            return

        if tile.get("cared_today"):
            return

        tile["cared_today"] = True

        return



def refresh_animals(
    farm: Any,
    *,
    current_day: int,
    context: SimulationContext,
) -> None:
    """
    Refresh animals on one farm for the end-of-day transition.
    """

    from estate_developer.simulation.reference_rules import (
        ANIMALS,
    )

    next_day = current_day + 1

    for y in range(context.board_size):
        for x in range(context.board_size):

            tile = farm.tiles[y][x]

            if not (
                isinstance(tile, dict)
                and "animal" in tile
            ):
                continue

            animal = tile.get("animal")

            if animal not in ANIMALS:
                continue

            if tile.get("fed_today"):
                tile["consecutive_unfed"] = 0
            else:
                tile["consecutive_unfed"] = (
                    int(
                        tile.get(
                            "consecutive_unfed",
                            0,
                        )
                    )
                    + 1
                )

            if tile["consecutive_unfed"] >= 2:
                farm.tiles[y][x] = {
                    "kind": ANIMALS[animal]["structure"]
                }
                continue

            animal_data = ANIMALS[animal]

            days_since_first = (
                next_day
                - int(tile["placed_day"])
                - int(animal_data["first_yield_day"])
            )

            interval = int(
                animal_data["interval"]
            )

            if (
                days_since_first >= 0
                and interval > 0
                and days_since_first % interval == 0
            ):
                bonus = int(
                    tile.pop(
                        "pending_care_bonus",
                        0,
                    )
                )

                tile["yield_units"] = min(
                    int(animal_data["max_held"]),
                    int(
                        tile.get(
                            "yield_units",
                            0,
                        )
                    )
                    + 1
                    + bonus,
                )

                tile["pending_care_bonus"] = 0

            if (
                tile.get("cared_today")
                and tile.get("fed_today")
            ):
                tile["pending_care_bonus"] = (
                    int(
                        tile.get(
                            "pending_care_bonus",
                            0,
                        )
                    )
                    + 1
                )

            tile["fertilizer_available"] = True
            tile["fed_today"] = False
            tile["cared_today"] = False




def drop_inventories_to_shed(
    private: Any,
    *,
    shed_capacity: int,
) -> None:
    """
    Move our visible actor inventories into our shared shed.

    The real environment only exposes our private inventory to the
    agent, so opponent-private inventory is intentionally not modeled
    here.
    """

    for inventory in private.inventories:

        for item, quantity in list(
            inventory.items()
        ):

            quantity = int(quantity)

            if quantity <= 0:
                del inventory[item]
                continue

            current = sum(
                int(value)
                for value in private.shed.values()
            )

            room = max(
                0,
                shed_capacity - current,
            )

            take = min(
                quantity,
                room,
            )

            if take > 0:
                private.shed[item] = (
                    private.shed.get(item, 0)
                    + take
                )

            # The real helper drops/discards inventory contents at
            # end of day rather than carrying them into the next day.
            del inventory[item]




def reset_workers(
    farm: Any,
    *,
    context: SimulationContext,
) -> None:
    """
    Reset one farm's farmer, hands, and daily hire counter.
    """

    half = context.board_size // 2

    from estate_developer.state.parser import Position

    object.__setattr__(
        farm,
        "farmer",
        Position(
            x=half - 1,
            y=half - 1,
        ),
    )

    object.__setattr__(
        farm,
        "hands",
        (),
    )

    object.__setattr__(
        farm,
        "hires_today",
        0,
    )



def unlock_town_shop(
    state: ObservationState,
    *,
    context: SimulationContext,
    rng: Any,
) -> None:
    """
    Unlock exactly one random shop every configured number of days.
    """

    next_day = state.day + 1

    if next_day <= 0:
        return

    if (
        next_day
        % context.town_shop_unlock_interval
        != 0
    ):
        return

    from estate_developer.simulation.reference_rules import (
        SHOPS,
    )

    unlocked = list(
        state.town.unlocked_shops
    )

    remaining = [
        shop
        for shop in sorted(SHOPS)
        if shop not in unlocked
    ]

    if not remaining:
        return

    choice = rng.choice(remaining)

    unlocked.append(choice)

    object.__setattr__(
        state,
        "town",
        type(state.town)(
            unlocked_shops=tuple(unlocked),
        ),
    )



def spawn_weeds(
    farm: Any,
    *,
    context: SimulationContext,
    rng: Any,
) -> None:
    """
    Spawn weeds on one farm using the shared RNG stream.
    """

    for y in range(context.board_size):
        for x in range(context.board_size):

            if (
                farm.tiles[y][x] is None
                and rng.random()
                < context.weed_spawn_chance
            ):
                farm.tiles[y][x] = {
                    "kind": "WEED"
                }




def end_of_day_refresh(
    state: ObservationState,
    *,
    context: SimulationContext,
    rng: Any,
) -> None:
    """
    Exact two-farm end-of-day refresh.

    The shared RNG must be consumed in the same order as the real
    Kaggriculture environment:

        farm 0 weed draws
        farm 1 weed draws
        town shop selection
    """

    current_day = state.day

    # IMPORTANT:
    # The real environment refreshes BOTH public farms before the
    # town-shop RNG draw. This is necessary for deterministic parity.
    for farm_id, farm in enumerate(state.farms):

        refresh_plants(
            farm,
            current_day=current_day,
            context=context,
        )

        refresh_animals(
            farm,
            current_day=current_day,
            context=context,
        )

        spawn_weeds(
            farm,
            context=context,
            rng=rng,
        )

        if farm_id == state.player:
            drop_inventories_to_shed(
                state.private,
                shed_capacity=context.shed_capacity,
            )

        reset_workers(
            farm,
            context=context,
        )

    # Our actor inventory starts the next day empty.
    object.__setattr__(
        state.private,
        "inventories",
        ({},),
    )

    # Town-shop selection happens AFTER both farms consumed the
    # shared RNG stream.
    unlock_town_shop(
        state,
        context=context,
        rng=rng,
    )



# ============================================================
# Stubs for later V11 phases
# ============================================================

def _parse_market_order(
    order: Any,
) -> dict[str, Any] | None:
    """Mirror Kaggriculture's market order parser."""

    if not isinstance(order, list) or not order:
        return None

    op = order[0]

    if op in ("HIRE", "BUY_LAND"):
        return {"type": op}

    if op not in (
        "BUY_SEED",
        "BUY_PRODUCT",
        "BUY_ANIMAL",
        "SELL",
    ):
        return None

    if len(order) < 3:
        return None

    try:
        quantity = int(order[2])
    except (TypeError, ValueError):
        return None

    if quantity <= 0:
        return None

    return {
        "type": op,
        "item": order[1],
        "remaining": quantity,
    }


def _commit_market_unit(
    state: ObservationState,
    player_id: int,
    op: str,
    item: str,
    price: int,
) -> bool:
    """
    Commit exactly one market unit using real Kaggriculture semantics.
    """

    farm = state.farms[player_id]
    private = (
        state.private
        if player_id == state.player
        else None
    )

    # The agent normally simulates its own private state. For the
    # opponent, ObservationState does not contain private information.
    # Therefore opponent market simulation must be handled separately
    # by the planner when opponent-private state is available.
    if private is None:
        return False

    if op == "SELL":
        if private.shed.get(item, 0) <= 0:
            return False

        private.shed[item] -= 1
        farm_money = farm.money + price

        object.__setattr__(
            farm,
            "money",
            farm_money,
        )

        # Real environment does not increase market inventory on
        # $1 sales.
        if price > 1:
            state.market.inventory[item] += 1

        return True

    if op == "BUY_PRODUCT":
        if farm.money < price:
            return False

        object.__setattr__(
            farm,
            "money",
            farm.money - price,
        )

        private.shed[item] = (
            private.shed.get(item, 0) + 1
        )

        state.market.inventory[item] -= 1
        return True

    if op == "BUY_SEED":
        if farm.money < price:
            return False

        object.__setattr__(
            farm,
            "money",
            farm.money - price,
        )

        private.seeds[item] = (
            private.seeds.get(item, 0) + 1
        )

        return True

    if op == "BUY_ANIMAL":
        if farm.money < price:
            return False

        object.__setattr__(
            farm,
            "money",
            farm.money - price,
        )

        private.shed[item] = (
            private.shed.get(item, 0) + 1
        )

        return True

    return False


def _hire_cost(
    hires_today: int,
    multiplier: int,
) -> int:
    """Exact Kaggriculture Fibonacci hire cost."""

    a, b = 1, 1

    for _ in range(hires_today):
        a, b = b, a + b

    return multiplier * a


def _spawn_hand_position(
    farm: Any,
    board_size: int,
) -> list[int]:
    """Exact Kaggriculture hand-spawn policy."""

    half = board_size // 2

    access_tiles = (
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    )

    occupants = {
        tile: 0
        for tile in access_tiles
    }

    all_positions = [
        (
            farm.farmer.x,
            farm.farmer.y,
        ),
        *[
            (p.x, p.y)
            for p in farm.hands
        ],
    ]

    for position in all_positions:
        if position in occupants:
            occupants[position] += 1

    best = sorted(
        occupants.items(),
        key=lambda pair: (
            pair[1],
            access_tiles.index(pair[0]),
        ),
    )

    return list(best[0][0])


def _do_hire(
    state: ObservationState,
    *,
    context: SimulationContext,
) -> None:
    """Exact HIRE semantics for our player."""

    farm = state.me
    private = state.private

    cost = _hire_cost(
        farm.hires_today,
        context.farm_hand_cost_mult,
    )

    if farm.money < cost:
        return

    object.__setattr__(
        farm,
        "money",
        farm.money - cost,
    )

    object.__setattr__(
        farm,
        "hires_today",
        farm.hires_today + 1,
    )

    hands = list(farm.hands)

    from estate_developer.state.parser import Position

    spawn = _spawn_hand_position(
        farm,
        context.board_size,
    )

    hands.append(
        Position(
            x=spawn[0],
            y=spawn[1],
        )
    )

    object.__setattr__(
        farm,
        "hands",
        tuple(hands),
    )

    inventories = list(private.inventories)
    inventories.append({})

    object.__setattr__(
        private,
        "inventories",
        tuple(inventories),
    )


def _do_buy_land(
    state: ObservationState,
    *,
    context: SimulationContext,
) -> None:
    """Exact BUY_LAND semantics for our player."""

    farm = state.me

    extra_unlocked = (
        len(farm.unlocked_quadrants) - 1
    )

    if extra_unlocked >= 3:
        return

    from estate_developer.simulation.reference_rules import (
        LAND_ORDER,
        LAND_PRICES,
    )

    price = LAND_PRICES[extra_unlocked]

    if farm.money < price:
        return

    object.__setattr__(
        farm,
        "money",
        farm.money - price,
    )

    quadrant = LAND_ORDER[extra_unlocked]

    unlocked = list(
        farm.unlocked_quadrants
    )
    unlocked.append(quadrant)

    object.__setattr__(
        farm,
        "unlocked_quadrants",
        tuple(unlocked),
    )

    half = context.board_size // 2

    for y in range(context.board_size):
        for x in range(context.board_size):

            if quadrant == "NE":
                target = y < half and x >= half
            elif quadrant == "SW":
                target = y >= half and x < half
            else:
                target = y >= half and x >= half

            if target and farm.tiles[y][x] == "LOCKED":
                farm.tiles[y][x] = None


def process_market(
    state: ObservationState,
    actions: list[list[Any]],
    *,
    context: SimulationContext,
) -> None:
    """
    Process our player's market queue with Kaggriculture semantics.

    This matches:
        1. atomic HIRE / BUY_LAND
        2. per-unit lockstep BUY/SELL processing
        3. one shared pre-commit market price for each unit
        4. price refresh after the entire market phase
    """

    from estate_developer.simulation.reference_rules import (
        ANIMALS,
        CROPS,
        MARKET_PARAMS,
        market_price,
    )

    queue = list(actions)[
        : context.max_market_orders_per_turn
    ]

    orders: list[dict[str, Any]] = []

    for raw in queue:
        parsed = _parse_market_order(raw)

        if parsed is not None:
            orders.append(parsed)

    # Atomic orders.
    for order in orders:

        if order["type"] == "HIRE":
            _do_hire(
                state,
                context=context,
            )
            order["remaining"] = 0

        elif order["type"] == "BUY_LAND":
            _do_buy_land(state, context=context)
            order["remaining"] = 0

    # Per-unit lockstep.
    while True:

        active = [
            order
            for order in orders
            if order.get("remaining", 0) > 0
        ]

        if not active:
            break

        committed_any = False

        # Quote all active orders against the SAME market state.
        quotes: list[
            tuple[dict[str, Any], int] | None
        ] = []

        for order in orders:

            if order.get("remaining", 0) <= 0:
                quotes.append(None)
                continue

            op = order["type"]
            item = order.get("item")

            if op == "SELL":
                if (
                    item in state.market.inventory
                    and item != "FERTILIZER"
                ):
                    price = market_price(
                        item,
                        state.market.inventory[item],
                        params=MARKET_PARAMS,
                    )
                    quotes.append((order, price))
                else:
                    order["remaining"] = 0
                    quotes.append(None)

            elif op == "BUY_PRODUCT":
                if item in state.market.inventory:
                    price = market_price(
                        item,
                        state.market.inventory[item],
                        params=MARKET_PARAMS,
                    )
                    quotes.append((order, price))
                else:
                    order["remaining"] = 0
                    quotes.append(None)

            elif op == "BUY_SEED":
                if item in CROPS:
                    quotes.append(
                        (
                            order,
                            int(
                                CROPS[item]["seed"]
                            ),
                        )
                    )
                else:
                    order["remaining"] = 0
                    quotes.append(None)

            elif op == "BUY_ANIMAL":
                if item in ANIMALS:
                    quotes.append(
                        (
                            order,
                            int(
                                ANIMALS[item]["cost"]
                            ),
                        )
                    )
                else:
                    order["remaining"] = 0
                    quotes.append(None)

            else:
                order["remaining"] = 0
                quotes.append(None)

        for quoted in quotes:

            if quoted is None:
                continue

            order, price = quoted

            ok = _commit_market_unit(
                state,
                state.player,
                order["type"],
                order["item"],
                price,
            )

            if ok:
                order["remaining"] -= 1
                committed_any = True
            else:
                order["remaining"] = 0

        if not committed_any:
            break

    # Refresh all visible prices after market processing.
    for item in state.market.inventory:
        if item in MARKET_PARAMS:
            state.market.prices[item] = market_price(
                item,
                state.market.inventory[item],
                params=MARKET_PARAMS,
            )


def consume_town_demand(
    state: ObservationState,
    *,
    context: SimulationContext,
) -> None:
    """
    Exact town consumption for the shared market.

    Shop demand occurs every town_shop_sell_interval turns.
    Town-center demand occurs every town_center_sell_interval turns.
    """

    from estate_developer.simulation.reference_rules import (
        SHOPS,
        TOWN_CENTER_PRODUCTS,
        TOWN_CENTER_DEMAND_SCHEDULE,
    )

    step = state.step
    day = step // context.turns_per_day

    market = state.market

    # --------------------------------------------------------
    # Town shops
    # --------------------------------------------------------

    if (
        step % context.town_shop_sell_interval
        == 0
    ):

        for shop_name in state.town.unlocked_shops:

            products = SHOPS[shop_name]

            multiplier = (
                2
                if len(products) == 1
                else 1
            )

            for item in products:

                market.inventory[item] = max(
                    0,
                    market.inventory[item]
                    - multiplier,
                )

    # --------------------------------------------------------
    # Town center
    # --------------------------------------------------------

    if (
        step % context.town_center_sell_interval
        == 0
    ):

        center_multiplier = 1

        for threshold, multiplier in (
            TOWN_CENTER_DEMAND_SCHEDULE
        ):
            if day >= threshold:
                center_multiplier = multiplier
                break

        for item in TOWN_CENTER_PRODUCTS:

            market.inventory[item] = max(
                0,
                market.inventory[item]
                - center_multiplier,
            )

    # --------------------------------------------------------
    # Refresh visible prices
    # --------------------------------------------------------

    from estate_developer.simulation.reference_rules import (
        MARKET_PARAMS,
        market_price,
    )

    for item in market.inventory:

        if item in MARKET_PARAMS:

            market.prices[item] = market_price(
                item,
                market.inventory[item],
                params=MARKET_PARAMS,
            )


def decay_plants(
    state: ObservationState,
    *,
    context: SimulationContext,
) -> None:
    """
    Exact Kaggriculture lifespan decay.

    When a plant reaches max_lifespan_step:
        every second step:
            yield_units -= 1

    When yield reaches zero:
        tile becomes WEED.
    """

    farm = state.me

    for y in range(context.board_size):
        for x in range(context.board_size):

            tile = farm.tiles[y][x]

            if not (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
            ):
                continue

            max_lifespan_step = int(
                tile.get(
                    "max_lifespan_step",
                    -1,
                )
            )

            if max_lifespan_step < 0:
                continue

            if state.step < max_lifespan_step:
                continue

            if (
                state.step - max_lifespan_step
            ) % 2 != 0:
                continue

            tile["yield_units"] = (
                int(
                    tile.get(
                        "yield_units",
                        0,
                    )
                )
                - 1
            )

            if tile["yield_units"] <= 0:
                farm.tiles[y][x] = {
                    "kind": "WEED"
                }


def _refresh_one_plant(
    tile: dict[str, Any],
    *,
    current_day: int,
    next_day: int,
    context: SimulationContext,
) -> bool:
    """
    Refresh one plant.

    Returns True if the caller should replace the tile with WEED.
    """

    was_watered = bool(
        tile.get("watered_today", False)
    )

    if was_watered:
        tile["consecutive_unwatered"] = 0
    else:
        tile["consecutive_unwatered"] = (
            int(
                tile.get(
                    "consecutive_unwatered",
                    0,
                )
            )
            + 1
        )

    tile["watered_today"] = False

    if tile["consecutive_unwatered"] >= 2:
        return True

    crop = str(tile["crop"])
    crop_data = CROPS[crop]

    # Non-ongoing crops gain yield directly when WATER is used
    # inside the qualifying window, so there is no production
    # calculation here.
    if not bool(crop_data["ongoing"]):
        return False

    days_since_first = (
        next_day
        - int(tile["planted_day"])
        - int(crop_data["first_yield_day"])
    )

    if days_since_first < 0:
        return False

    interval = int(crop_data["interval"])

    if interval <= 0:
        return False

    if days_since_first % interval != 0:
        return False

    production_count = (
        days_since_first // interval
        + 1
    )

    if (
        production_count
        > int(crop_data["max_yield"])
    ):
        return False

    fertilized = (
        was_watered
        and int(
            tile.get(
                "fertilized_until_day",
                -1,
            )
        ) >= current_day
    )

    tile["yield_units"] = min(
        int(crop_data["max_yield"]),
        int(
            tile.get(
                "yield_units",
                0,
            )
        )
        + (2 if fertilized else 1),
    )

    if (
        production_count
        == int(crop_data["max_yield"])
    ):
        tile["max_lifespan_step"] = (
            (next_day + 1)
            * context.turns_per_day
        )

    return False



def refresh_plants(
    farm: Any,
    *,
    current_day: int,
    context: SimulationContext,
) -> None:
    """
    Refresh plants on one farm for the end-of-day transition.
    """

    next_day = current_day + 1

    for y in range(context.board_size):
        for x in range(context.board_size):

            tile = farm.tiles[y][x]

            if not (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
            ):
                continue

            should_be_weed = _refresh_one_plant(
                tile,
                current_day=current_day,
                next_day=next_day,
                context=context,
            )

            if should_be_weed:
                farm.tiles[y][x] = {
                    "kind": "WEED"
                }




def end_of_day_refresh(
    state: ObservationState,
    *,
    context: SimulationContext,
    rng: Any,
) -> None:
    """
    Exact two-farm end-of-day refresh.

    The shared RNG must be consumed in the same order as the real
    Kaggriculture environment:

        farm 0 weed draws
        farm 1 weed draws
        town shop selection
    """

    current_day = state.day

    # IMPORTANT:
    # The real environment refreshes BOTH public farms before the
    # town-shop RNG draw. This is necessary for deterministic parity.
    for farm_id, farm in enumerate(state.farms):

        refresh_plants(
            farm,
            current_day=current_day,
            context=context,
        )

        refresh_animals(
            farm,
            current_day=current_day,
            context=context,
        )

        spawn_weeds(
            farm,
            context=context,
            rng=rng,
        )

        if farm_id == state.player:
            drop_inventories_to_shed(
                state.private,
                shed_capacity=context.shed_capacity,
            )

        reset_workers(
            farm,
            context=context,
        )

    # Our actor inventory starts the next day empty.
    object.__setattr__(
        state.private,
        "inventories",
        ({},),
    )

    # Town-shop selection happens AFTER both farms consumed the
    # shared RNG stream.
    unlock_town_shop(
        state,
        context=context,
        rng=rng,
    )



def step_state(
    state: ObservationState,
    action: dict[str, Any],
    *,
    context: SimulationContext | None = None,
) -> ObservationState:
    """
    Complete reference-faithful V11 one-step transition.

    Returns a new state and does not mutate the caller's state.
    """

    if context is None:
        context = SimulationContext()

    next_state = copy_observation(state)

    # --------------------------------------------------------
    # Current step/day as used by Kaggriculture interpreter.
    # --------------------------------------------------------

    current_step = next_state.step
    current_day = (
        current_step
        // context.turns_per_day
    )

    # --------------------------------------------------------
    # 1. Farmer + hand actions
    # --------------------------------------------------------

    farmer_action = action.get(
        "farmer",
        ["PASS"],
    )

    if not isinstance(
        farmer_action,
        list,
    ):
        farmer_action = ["PASS"]

    hands_actions = action.get(
        "hands",
        [],
    )

    if not isinstance(
        hands_actions,
        list,
    ):
        hands_actions = []

    unit_actions = [
        farmer_action,
        *hands_actions,
    ]

    # Match reference atomic PLANT validation:
    # if aggregate requests exceed available seeds,
    # ALL PLANT requests for that crop become PASS.
    plant_demand: dict[str, int] = {}

    for unit_action in unit_actions:

        if (
            isinstance(unit_action, list)
            and len(unit_action) >= 2
            and unit_action[0] == "PLANT"
        ):

            crop = str(unit_action[1])

            plant_demand[crop] = (
                plant_demand.get(crop, 0)
                + 1
            )

    blocked_crops = {
        crop
        for crop, demand in plant_demand.items()
        if demand
        > next_state.private.seeds.get(
            crop,
            0,
        )
    }

    def allowed(unit_action):
        if (
            isinstance(unit_action, list)
            and len(unit_action) >= 2
            and unit_action[0] == "PLANT"
            and str(unit_action[1])
            in blocked_crops
        ):
            return ["PASS"]

        return unit_action

    apply_unit_action(
        next_state,
        allowed(farmer_action),
        unit_index=0,
        context=context,
    )

    for hand_idx, hand_action in enumerate(
        hands_actions
    ):

        apply_unit_action(
            next_state,
            allowed(hand_action),
            unit_index=hand_idx + 1,
            context=context,
        )

    # --------------------------------------------------------
    # 2. Market
    # --------------------------------------------------------

    market_actions = action.get(
        "market",
        [],
    )

    if not isinstance(
        market_actions,
        list,
    ):
        market_actions = []

    process_market(
        next_state,
        market_actions,
        context=context,
    )

    # --------------------------------------------------------
    # 3. Town consumption
    # --------------------------------------------------------

    consume_town_demand(
        next_state,
        context=context,
    )

    # --------------------------------------------------------
    # 4. Plant lifespan decay
    # --------------------------------------------------------

    decay_plants(
        next_state,
        context=context,
    )

    # --------------------------------------------------------
    # 5. End-of-day refresh
    #
    # Reference fires this when:
    #       (step + 1) % turns_per_day == 0
    # --------------------------------------------------------

    is_end_of_day = (
        (current_step + 1)
        % context.turns_per_day
        == 0
    )

    if is_end_of_day:

        if context.seed is None:
            # Observation-only planning does not know the hidden
            # competition seed. Use a deterministic local RNG so
            # rollouts remain reproducible.
            seed_value = 0
        else:
            seed_value = int(context.seed)

        import random

        day_rng = random.Random(
            (seed_value * 1_000_003)
            ^ current_day
        )

        end_of_day_refresh(
            next_state,
            context=context,
            rng=day_rng,
        )

    # --------------------------------------------------------
    # 6. Advance time
    # --------------------------------------------------------

    next_step = current_step + 1
    next_day = (
        next_step
        // context.turns_per_day
    )
    next_hour = (
        next_step
        % context.turns_per_day
    )

    object.__setattr__(
        next_state,
        "step",
        next_step,
    )

    object.__setattr__(
        next_state,
        "day",
        next_day,
    )

    object.__setattr__(
        next_state,
        "hour",
        next_hour,
    )

    return next_state
