from __future__ import annotations

from estate_developer.state.parser import ObservationState
from estate_developer.economics.crops import CROP_PROFILES


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
    V9 Rich Terminal Value.

    Estimates the total economic value of a state by summing:
      1. Cash on hand
      2. Shed inventory at current market price
      3. Expected remaining crop revenue (plants in ground)
      4. Expected remaining animal revenue (animals in production)
      5. Competitive edge bonus (win probability proxy)
    """

    @staticmethod
    def calculate(state: ObservationState) -> float:
        value = float(state.me.money)

        market_prices = state.market.prices
        current_day = int(state.day)

        # -------------------------------------------------------
        # 1. Shed inventory at current market price
        # -------------------------------------------------------
        for item, qty in state.private.shed.items():
            if qty <= 0:
                continue
            if item in CROP_PROFILES:
                price = float(market_prices.get(item, CROP_PROFILES[item].base_price))
            elif item in PRODUCT_BASE_PRICES:
                price = float(market_prices.get(item, PRODUCT_BASE_PRICES[item]))
            else:
                price = float(market_prices.get(item, 1))
            value += price * qty

        # -------------------------------------------------------
        # 2. Farmer inventory
        # -------------------------------------------------------
        for inv in state.private.inventories:
            for item, qty in inv.items():
                if qty <= 0:
                    continue
                if item in CROP_PROFILES:
                    price = float(market_prices.get(item, CROP_PROFILES[item].base_price))
                elif item in PRODUCT_BASE_PRICES:
                    price = float(market_prices.get(item, PRODUCT_BASE_PRICES[item]))
                else:
                    price = float(market_prices.get(item, 1))
                value += price * qty

        # -------------------------------------------------------
        # 3. Crops in ground — expected future harvest value
        # -------------------------------------------------------
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
                    price = float(market_prices.get(crop, profile.base_price))

                    if profile.yield_type == "ONE_TIME":
                        # Already harvestable yield
                        if yield_units > 0:
                            value += yield_units * price
                        else:
                            # Not yet ready — estimate at 60% of max
                            # (discounted for time risk and execution cost)
                            est = profile.max_yield_unfertilized * 0.6
                            value += est * price
                    else:
                        # Ongoing crop: estimate remaining scheduled yields
                        if yield_units > 0:
                            value += yield_units * price
                        # Ongoing crops have limited remaining yields;
                        # conservatively add 1 more yield at 50% discount
                        value += price * 0.5

                # -----------------------------------------------
                # 4. Animals in production
                # -----------------------------------------------
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

                    # Value of unharvested product
                    value += yield_units * price

                    # Estimate future yields until end of season
                    interval = ANIMAL_YIELD_INTERVALS.get(animal, 1)
                    remaining_days = max(0, SEASON_DAYS - current_day)
                    future_yields = remaining_days // interval

                    # Discount future animal yields by 50% for
                    # execution risk (feeding, harvesting, selling)
                    value += future_yields * price * 0.5

        # -------------------------------------------------------
        # 5. Competitive edge bonus
        # -------------------------------------------------------
        opponent_cash = float(state.opponent.money)
        cash_lead = value - opponent_cash
        if cash_lead > 0:
            # Small win-probability bonus — being ahead is valuable
            value += min(cash_lead * 0.05, 200)

        return value

