from __future__ import annotations

from typing import Any

from estate_developer.state.parser import ObservationState, FarmState, PrivateState, Position
from estate_developer.economics.crops import CROP_PROFILES


def apply_action(state: ObservationState, action_dict: dict[str, Any]) -> None:
    """
    Applies an action dictionary to the observation state in place.
    The action_dict should follow the format returned by the agent:
    {
        "farmer": ["ACTION_NAME", arg1, ...],
        "hands": [["ACTION_NAME", arg1, ...], ...],
        "market": [["MARKET_ACTION", arg1, ...], ...]
    }
    """
    player_farm = state.me
    private_state = state.private

    # Process Market Actions
    market_actions = action_dict.get("market", [])
    for m_act in market_actions:
        if not m_act:
            continue
        op = m_act[0]
        if op in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT"):
            item = m_act[1]
            qty = int(m_act[2])
            
            cost = 0
            if op == "BUY_SEED":
                cost = CROP_PROFILES.get(item, type("obj", (object,), {"seed_cost": 0})()).seed_cost * qty
            elif op == "BUY_ANIMAL":
                # Static costs for animals based on README
                animal_costs = {"GOOSE": 300, "SHEEP": 500, "COW": 400}
                cost = animal_costs.get(item, 0) * qty
            elif op == "BUY_PRODUCT":
                # Only WHEAT and FERTILIZER can be bought from market dynamically
                # This is a simplification; a full sim would ask MarketManager for dynamic price.
                product_costs = {"WHEAT": 25, "FERTILIZER": 100}
                cost = product_costs.get(item, 25) * qty
                
            if player_farm.money >= cost:
                object.__setattr__(player_farm, "money", player_farm.money - cost)
                if op == "BUY_SEED":
                    private_state.seeds[item] = private_state.seeds.get(item, 0) + qty
                elif op in ("BUY_ANIMAL", "BUY_PRODUCT"):
                    private_state.shed[item] = private_state.shed.get(item, 0) + qty

        elif op == "SELL":
            item = m_act[1]
            qty = int(m_act[2])
            in_shed = private_state.shed.get(item, 0)
            sell_qty = min(qty, in_shed)
            if sell_qty > 0:
                from estate_developer.economics.market_manager import MarketManager
                manager = MarketManager()
                current_inv = state.market.inventory.get(item, manager.I0)
                unit_price = state.market.prices.get(item, manager.calculate_price(item, current_inv))
                revenue = unit_price * sell_qty
                object.__setattr__(player_farm, "money", player_farm.money + revenue)
                private_state.shed[item] -= sell_qty
                # Update simulated market inventory if present
                state.market.inventory[item] = current_inv + sell_qty
                # We could recalculate state.market.prices here, but for rollout we leave it or approximate it
                state.market.prices[item] = manager.calculate_price(item, state.market.inventory[item])
                
        elif op == "BUY_LAND":
            # Simplification: deduct $1000 for simplicity in this stub.
            if player_farm.money >= 1000:
                object.__setattr__(player_farm, "money", player_farm.money - 1000)
                quads = list(player_farm.unlocked_quadrants)
                if len(quads) < 4:
                    quads.append("NEW")
                object.__setattr__(player_farm, "unlocked_quadrants", tuple(quads))
                
        elif op == "HIRE":
            hires = player_farm.hires_today
            cost = 1 # Simplified fibonacci
            if player_farm.money >= cost:
                object.__setattr__(player_farm, "money", player_farm.money - cost)
                object.__setattr__(player_farm, "hires_today", hires + 1)
                hands = list(player_farm.hands)
                hands.append(Position(4, 4)) # Default spawn
                object.__setattr__(player_farm, "hands", tuple(hands))

    # Process Farmer Action
    farmer_act = action_dict.get("farmer", ["PASS"])
    _apply_field_action(player_farm, private_state, farmer_act, is_farmer=True)

    # Process Hand Actions
    hands_acts = action_dict.get("hands", [])
    for idx, h_act in enumerate(hands_acts):
        _apply_field_action(player_farm, private_state, h_act, is_farmer=False, hand_idx=idx)


def _apply_field_action(farm: FarmState, private: PrivateState, act: list[Any], is_farmer: bool, hand_idx: int = 0) -> None:
    if not act or act[0] == "PASS":
        return

    op = act[0]
    
    if op == "PLANT":
        crop = act[1]
        x, y = int(act[2]), int(act[3])
        if private.seeds.get(crop, 0) > 0:
            private.seeds[crop] -= 1
            tile = farm.tiles[y][x]
            if isinstance(tile, dict) and tile.get("kind") == "SOIL":
                # Plant the seed
                farm.tiles[y][x] = {
                    "kind": "PLANT",
                    "crop": crop,
                    "age": 0,
                    "yield_units": 0,
                    "watered_today": False,
                    "consecutive_unwatered": 0
                }
            if is_farmer:
                object.__setattr__(farm, "farmer", Position(x, y))
            else:
                hands = list(farm.hands)
                if hand_idx < len(hands):
                    hands[hand_idx] = Position(x, y)
                object.__setattr__(farm, "hands", tuple(hands))

    elif op == "WATER":
        x, y = int(act[1]), int(act[2])
        tile = farm.tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            tile["watered_today"] = True
            tile["consecutive_unwatered"] = 0
        if is_farmer:
            object.__setattr__(farm, "farmer", Position(x, y))
        else:
            hands = list(farm.hands)
            if hand_idx < len(hands):
                hands[hand_idx] = Position(x, y)
            object.__setattr__(farm, "hands", tuple(hands))

    elif op == "HARVEST":
        x, y = int(act[1]), int(act[2])
        tile = farm.tiles[y][x]
        if isinstance(tile, dict):
            if tile.get("kind") == "PLANT":
                crop = tile["crop"]
                yield_units = tile.get("yield_units", 0)
                if yield_units > 0:
                    if is_farmer:
                        inv = private.inventories[0] if private.inventories else {}
                        inv[crop] = inv.get(crop, 0) + yield_units
                        if not private.inventories:
                            object.__setattr__(private, "inventories", (inv,))
                    else:
                        private.shed[crop] = private.shed.get(crop, 0) + yield_units
                    
                    profile = CROP_PROFILES.get(crop)
                    if profile and profile.yield_type == "ONE_TIME":
                        farm.tiles[y][x] = {"kind": "SOIL"}
                    else:
                        tile["yield_units"] = 0
            elif tile.get("kind") in ("COOP", "PASTURE"):
                animal = tile.get("animal")
                yield_units = tile.get("yield_units", 0)
                if yield_units > 0 and animal:
                    product = "EGG" if animal == "GOOSE" else ("MILK" if animal == "COW" else "WOOL")
                    if is_farmer:
                        inv = private.inventories[0] if private.inventories else {}
                        inv[product] = inv.get(product, 0) + yield_units
                        if not private.inventories:
                            object.__setattr__(private, "inventories", (inv,))
                    else:
                        private.shed[product] = private.shed.get(product, 0) + yield_units
                    tile["yield_units"] = 0

        if is_farmer:
            object.__setattr__(farm, "farmer", Position(x, y))
        else:
            hands = list(farm.hands)
            if hand_idx < len(hands):
                hands[hand_idx] = Position(x, y)
            object.__setattr__(farm, "hands", tuple(hands))

    elif op in ("BUILD_COOP", "BUILD_PASTURE"):
        x, y = int(act[1]), int(act[2])
        tile = farm.tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "SOIL":
            kind = "COOP" if op == "BUILD_COOP" else "PASTURE"
            farm.tiles[y][x] = {
                "kind": kind,
                "animal": None,
                "yield_units": 0,
                "fed_today": False,
                "consecutive_unfed": 0,
                "cared_today": False,
                "fertilizer_available": False,
                "pending_care_bonus": 0
            }
        
    elif op == "DIG":
        x, y = int(act[1]), int(act[2])
        tile = farm.tiles[y][x]
        if isinstance(tile, dict):
            # Only empty structures, plants, weeds can be dug
            if tile.get("kind") in ("PLANT", "WEED"):
                farm.tiles[y][x] = {"kind": "SOIL"}
            elif tile.get("kind") in ("COOP", "PASTURE") and not tile.get("animal"):
                farm.tiles[y][x] = {"kind": "SOIL"}

    elif op == "FEED":
        x, y = int(act[1]), int(act[2])
        tile = farm.tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
            # Requires wheat
            has_wheat = False
            if is_farmer and private.inventories:
                if private.inventories[0].get("WHEAT", 0) > 0:
                    private.inventories[0]["WHEAT"] -= 1
                    has_wheat = True
            elif private.shed.get("WHEAT", 0) > 0: # Hands take from shed conceptually if nearby, or we just allow it
                private.shed["WHEAT"] -= 1
                has_wheat = True
                
            if has_wheat:
                tile["fed_today"] = True
                tile["consecutive_unfed"] = 0

    elif op == "CARE":
        x, y = int(act[1]), int(act[2])
        tile = farm.tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
            tile["cared_today"] = True

    elif op == "COLLECT_FERTILIZER":
        x, y = int(act[1]), int(act[2])
        tile = farm.tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
            if tile.get("fertilizer_available"):
                tile["fertilizer_available"] = False
                if is_farmer:
                    inv = private.inventories[0] if private.inventories else {}
                    inv["FERTILIZER"] = inv.get("FERTILIZER", 0) + 1
                    if not private.inventories:
                        object.__setattr__(private, "inventories", (inv,))
                else:
                    private.shed["FERTILIZER"] = private.shed.get("FERTILIZER", 0) + 1

    elif op == "FERTILIZE":
        x, y = int(act[1]), int(act[2])
        tile = farm.tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            has_fert = False
            if is_farmer and private.inventories:
                if private.inventories[0].get("FERTILIZER", 0) > 0:
                    private.inventories[0]["FERTILIZER"] -= 1
                    has_fert = True
            elif private.shed.get("FERTILIZER", 0) > 0:
                private.shed["FERTILIZER"] -= 1
                has_fert = True
                
            if has_fert:
                tile["fertilized_until_day"] = state.day + 3 # Needs global state day reference, passing for simple sim

    elif op == "PLACE":
        # Moving items from inventory to shed
        if is_farmer and private.inventories:
            inv = private.inventories[0]
            for c, q in inv.items():
                if q > 0:
                    private.shed[c] = private.shed.get(c, 0) + q
            inv.clear()


def tick_environment(state: ObservationState) -> None:
    """
    Simulates the passage of one tick (e.g. crop growth, day boundary).
    """
    new_step = state.step + 1
    object.__setattr__(state, "step", new_step)
    
    # 24 steps per day assumption
    new_day = new_step // 24
    new_hour = new_step % 24
    is_new_day = (new_day > state.day)
    
    object.__setattr__(state, "day", new_day)
    object.__setattr__(state, "hour", new_hour)
    
    # Process market drain on day boundary
    if is_new_day:
        for item in list(state.market.inventory.keys()):
            current = state.market.inventory[item]
            consumed = max(1, int(current * 0.05)) # Approximate town consumption
            state.market.inventory[item] = max(0, current - consumed)
            
    # Process farms
    for farm in state.farms:
        for y in range(len(farm.tiles)):
            for x in range(len(farm.tiles[y])):
                tile = farm.tiles[y][x]
                if not isinstance(tile, dict):
                    continue
                
                kind = tile.get("kind")
                if kind == "PLANT" and is_new_day:
                    if tile.get("watered_today"):
                        tile["age"] = tile.get("age", 0) + 1
                        tile["consecutive_unwatered"] = 0
                        
                        crop = tile.get("crop")
                        profile = CROP_PROFILES.get(crop)
                        if profile:
                            age = tile["age"]
                            if age == profile.time_to_first_yield:
                                tile["yield_units"] = profile.max_yield
                            elif profile.subsequent_yields and age > profile.time_to_first_yield:
                                tile["yield_units"] = profile.max_yield
                    else:
                        tile["consecutive_unwatered"] = tile.get("consecutive_unwatered", 0) + 1
                        if tile["consecutive_unwatered"] >= 3:
                            farm.tiles[y][x] = {"kind": "WEED"}
                            
                    tile["watered_today"] = False
                    
                elif kind in ("COOP", "PASTURE") and is_new_day:
                    animal = tile.get("animal")
                    if animal:
                        if tile.get("fed_today"):
                            tile["consecutive_unfed"] = 0
                            tile["yield_units"] = tile.get("yield_units", 0) + 1
                            if not tile.get("fertilizer_available"):
                                tile["fertilizer_available"] = True
                        else:
                            tile["consecutive_unfed"] = tile.get("consecutive_unfed", 0) + 1
                            if tile["consecutive_unfed"] >= 3:
                                tile["animal"] = None
                                tile["yield_units"] = 0
                                
                        tile["fed_today"] = False
                        tile["cared_today"] = False
