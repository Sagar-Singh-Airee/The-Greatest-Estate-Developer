"""
V9 Town Demand Forecaster.

Predicts how town shop consumption will drain market inventory
over the next N days, allowing the agent to anticipate price
increases and time its sales perfectly.

Shop consumption rates (from Kaggriculture README):
- Each shop instance consumes products every townShopSellInterval=4 turns
  → 6 times per day per shop instance.
- Single-product shops consume 2x.
- Town center consumes 1 of every product once per day (every 24 turns).

Shop demand mappings (products consumed per shop type per tick):
  BAKERY       : EGG×1, WHEAT×1
  PIZZA_SHOP   : MILK×1, TOMATO×1, WHEAT×1
  BRUNCH_SPOT  : EGG×1, WHEAT×1, STRAWBERRY×1
  YARN_STORE   : WOOL×2
  ICE_CREAM    : STRAWBERRY×1, MILK×1, WHEAT×1
  PET_CAFE     : CARROT×2
  SMOOTHIE     : STRAWBERRY×1, MILK×1
  FARMERS_MRKT : WHEAT×1, CARROT×1, TOMATO×1, STRAWBERRY×1
"""

from __future__ import annotations

SHOP_DEMAND: dict[str, dict[str, int]] = {
    "BAKERY":         {"EGG": 1, "WHEAT": 1},
    "PIZZA_SHOP":     {"MILK": 1, "TOMATO": 1, "WHEAT": 1},
    "BRUNCH_SPOT":    {"EGG": 1, "WHEAT": 1, "STRAWBERRY": 1},
    "YARN_STORE":     {"WOOL": 2},
    "ICE_CREAM_SHOP": {"STRAWBERRY": 1, "MILK": 1, "WHEAT": 1},
    "PET_CAFE":       {"CARROT": 2},
    "SMOOTHIE_SHOP":  {"STRAWBERRY": 1, "MILK": 1},
    "FARMERS_MARKET": {"WHEAT": 1, "CARROT": 1, "TOMATO": 1, "STRAWBERRY": 1},
}

# Town center removes 1 of every product per day
TOWN_CENTER_DAILY: int = 1

# Ticks per day
TICKS_PER_DAY: int = 24

# Shop consumes every N ticks
SHOP_SELL_INTERVAL: int = 4

# Shop ticks per day = 24 / 4 = 6
SHOP_TICKS_PER_DAY: int = TICKS_PER_DAY // SHOP_SELL_INTERVAL


class TownDemandForecaster:
    """
    Forecasts per-product market inventory drain from the town
    and returns predicted future prices.
    """

    def __init__(self, market_manager=None):
        self._market = market_manager

    def daily_drain_rates(self, unlocked_shops: list[str]) -> dict[str, float]:
        """
        Compute units-per-day drained from market inventory by town
        for the current shop configuration.
        """
        rates: dict[str, float] = {}

        # Town center: 1 unit of every product per day
        for product in (
            "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
            "EGG", "MILK", "WOOL",
        ):
            rates[product] = rates.get(product, 0.0) + TOWN_CENTER_DAILY

        # Shops: each instance consumes SHOP_TICKS_PER_DAY times per day
        for shop in unlocked_shops:
            demand = SHOP_DEMAND.get(shop, {})
            for product, qty in demand.items():
                rates[product] = (
                    rates.get(product, 0.0) + qty * SHOP_TICKS_PER_DAY
                )

        return rates

    def predict_inventory(
        self,
        resource: str,
        current_inventory: int,
        days_ahead: int,
        unlocked_shops: list[str],
    ) -> int:
        """
        Predict the market inventory of a resource N days from now,
        assuming no player activity (conservative estimate).
        """
        rates = self.daily_drain_rates(unlocked_shops)
        drain_per_day = rates.get(resource, 0.0)
        predicted = current_inventory - drain_per_day * days_ahead
        return max(1, int(predicted))

    def predict_price(
        self,
        resource: str,
        current_inventory: int,
        days_ahead: int,
        unlocked_shops: list[str],
    ) -> float:
        """
        Predict the sell price of a resource N days from now.
        Requires market_manager for the price curve calculation.
        """
        if self._market is None:
            return 0.0

        predicted_inv = self.predict_inventory(
            resource, current_inventory, days_ahead, unlocked_shops
        )
        return float(self._market.calculate_price(resource, predicted_inv))

    def should_hold(
        self,
        resource: str,
        current_inventory: int,
        current_price: float,
        unlocked_shops: list[str],
        days_ahead: int = 3,
        hold_threshold: float = 1.15,
    ) -> bool:
        """
        Returns True if the predicted price in `days_ahead` days is
        at least `hold_threshold` × the current price.
        Holding is only worthwhile if the gain covers the time cost.
        """
        predicted = self.predict_price(
            resource, current_inventory, days_ahead, unlocked_shops
        )
        return predicted >= current_price * hold_threshold
