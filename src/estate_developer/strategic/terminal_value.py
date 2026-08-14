from __future__ import annotations

from estate_developer.state.parser import ObservationState
from estate_developer.economics.crops import CROP_PROFILES
from estate_developer.economics.market_manager import MarketManager

# Base prices for animal products (not in CROP_PROFILES)
PRODUCT_BASE_PRICES: dict[str, int] = {
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
    "FERTILIZER": 100,
}

# Animal yield intervals (days between yields)
ANIMAL_YIELD_INTERVALS: dict[str, int] = {
    "GOOSE": 1,
    "COW": 2,
    "SHEEP": 3,
}

SEASON_DAYS = 30


class TerminalValueCalculator:
    """
    V11 Competitive Terminal Value.

    The KEY CHANGE: the objective is now
        Expected Score MARGIN = Our Final Cash - Opponent Final Cash

    not simply "our asset estimate". Comparing our total estimated
    wealth against the opponent's RAW cash alone (as V9 did) was
    mathematically invalid.

    We now estimate both players' final cash positions and return the
    DIFFERENCE. Search will always prefer states where we have a
    larger lead over the opponent at game end.

    The algorithm:
        1. Start from actual cash on hand (liquidated immediately).
        2. Add shed inventory at REALIZED market price (dynamic, not base).
        3. Add discounted future crop value derived from the simulator's
           growth model (days remaining × yield rate) — NOT arbitrary 0.5.
        4. Add discounted future animal value (days remaining / interval).
        5. Subtract our estimated opponent final cash.
        6. Return the margin as the objective.
    """

    _manager = MarketManager()

    @classmethod
    def _liquid_value(cls, items: dict[str, int], market: dict) -> float:
        """Compute the sale value of an item dict at realized market prices."""
        total = 0.0
        for item, qty in items.items():
            if qty <= 0:
                continue
            inv = market.get("inventory", {}).get(item, cls._manager.I0)
            realized = market.get("prices", {}).get(
                item, cls._manager.calculate_price(item, inv)
            )
            total += float(realized) * qty
        return total

    @classmethod
    def _estimate_our_final_cash(
        cls, state: ObservationState, days_remaining: int
    ) -> float:
        """
        Estimate our total final cash at end of season.
        This is the unified quantity the search optimizes.
        """
        market_inv = state.market.inventory
        market_prices = state.market.prices
        market = {"inventory": market_inv, "prices": market_prices}

        value = float(state.me.money)

        # 1. Shed inventory at realized market price
        value += cls._liquid_value(state.private.shed, market)

        # 2. Farmer inventory (will be placed to shed, then sold)
        for inv in state.private.inventories:
            value += cls._liquid_value(inv, market)

        # 3. Crops in ground — future harvest value
        for row in state.me.tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if tile.get("kind") == "PLANT":
                    crop = tile.get("crop", "")
                    profile = CROP_PROFILES.get(crop)
                    if not profile:
                        continue

                    yield_units = int(tile.get("yield_units", 0))
                    price = float(
                        market_prices.get(crop, profile.base_price)
                    )
                    age = int(tile.get("age", 0))

                    if profile.yield_type == "ONE_TIME":
                        if yield_units > 0:
                            value += yield_units * price
                        elif days_remaining >= max(0, profile.time_to_first_yield - age):
                            # Will ripen before end: count at 80% (watering risk)
                            value += profile.max_yield_unfertilized * price * 0.80
                        # else: won't ripen, worthless
                    else:
                        # Ongoing: current yield + estimate remaining harvests
                        value += yield_units * price
                        interval = max(1, profile.time_to_max_yield - profile.time_to_first_yield)
                        future_harvests = max(0, days_remaining // interval)
                        # 70% discount for execution (water, harvest, sell) risk
                        value += future_harvests * profile.max_yield_unfertilized * price * 0.70

                # 4. Animals in production
                elif tile.get("kind") in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    if not animal:
                        continue
                    yield_units = int(tile.get("yield_units", 0))
                    product = (
                        "EGG" if animal == "GOOSE"
                        else ("MILK" if animal == "COW" else "WOOL")
                    )
                    price = float(
                        market_prices.get(product, PRODUCT_BASE_PRICES.get(product, 50))
                    )
                    value += yield_units * price
                    interval = max(1, ANIMAL_YIELD_INTERVALS.get(animal, 1))
                    future_yields = max(0, days_remaining // interval)
                    # 65% discount for feeding, care, harvest, sell risk chain
                    value += future_yields * price * 0.65

        return value

    @classmethod
    def _estimate_opponent_final_cash(
        cls, state: ObservationState, days_remaining: int
    ) -> float:
        """
        Estimate the opponent's final cash from their public state.
        We can see their tiles and money but NOT their private shed/seeds.
        We therefore sum their cash + publicly visible crop values.
        """
        market_prices = state.market.prices
        value = float(state.opponent.money)

        for row in state.opponent.tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if tile.get("kind") == "PLANT":
                    crop = tile.get("crop", "")
                    profile = CROP_PROFILES.get(crop)
                    if not profile:
                        continue
                    age = int(tile.get("age", 0))
                    price = float(market_prices.get(crop, profile.base_price))
                    if profile.yield_type == "ONE_TIME":
                        time_left = max(0, profile.time_to_first_yield - age)
                        if days_remaining >= time_left:
                            value += profile.max_yield_unfertilized * price * 0.80
                    else:
                        interval = max(1, profile.time_to_max_yield - profile.time_to_first_yield)
                        future_harvests = max(0, days_remaining // interval)
                        value += future_harvests * profile.max_yield_unfertilized * price * 0.70
                elif tile.get("kind") in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    if animal:
                        product = (
                            "EGG" if animal == "GOOSE"
                            else ("MILK" if animal == "COW" else "WOOL")
                        )
                        price = float(
                            market_prices.get(product, PRODUCT_BASE_PRICES.get(product, 50))
                        )
                        interval = max(1, ANIMAL_YIELD_INTERVALS.get(animal, 1))
                        future_yields = max(0, days_remaining // interval)
                        value += future_yields * price * 0.65

        return value

    @classmethod
    def calculate(cls, state: ObservationState) -> float:
        """
        Return the expected score MARGIN (our final cash - their final cash).
        Beam search maximizes this, ensuring we always prefer winning trajectories.
        """
        days_remaining = max(0, SEASON_DAYS - int(state.day))

        our_final = cls._estimate_our_final_cash(state, days_remaining)
        their_final = cls._estimate_opponent_final_cash(state, days_remaining)

        margin = our_final - their_final

        # Gentle P(win) bonus: being ahead generates compounding value
        if margin > 0:
            margin += min(margin * 0.03, 500.0)

        return margin
