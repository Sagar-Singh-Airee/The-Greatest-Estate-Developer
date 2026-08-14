"""Short-horizon, rule-faithful town-demand forecasting."""

from __future__ import annotations

from estate_developer.simulation.reference_rules import (
    SHOPS,
    TOWN_CENTER_DEMAND_SCHEDULE,
    TOWN_CENTER_PRODUCTS,
    TOWN_CENTER_SELL_INTERVAL,
    TOWN_SHOP_SELL_INTERVAL,
    TURNS_PER_DAY,
)


class TownDemandForecaster:
    """Forecast market drain without inventing demand that the game lacks."""

    def __init__(self, market_manager=None):
        self._market = market_manager

    @staticmethod
    def _center_daily_rate(day: int) -> int:
        """Mirror the day-based multiplier in ``consume_town_demand``."""
        for threshold, multiplier in TOWN_CENTER_DEMAND_SCHEDULE:
            if day >= threshold:
                return multiplier
        return 1

    def daily_drain_rates(
        self,
        unlocked_shops: list[str] | tuple[str, ...],
        *,
        current_day: int = 0,
    ) -> dict[str, float]:
        rates = {
            product: float(self._center_daily_rate(current_day))
            for product in TOWN_CENTER_PRODUCTS
        }

        shop_ticks = TURNS_PER_DAY // TOWN_SHOP_SELL_INTERVAL
        for shop in unlocked_shops:
            products = SHOPS.get(shop, ())
            multiplier = 2 if len(products) == 1 else 1
            for product in products:
                rates[product] = rates.get(product, 0.0) + (
                    multiplier * shop_ticks
                )

        return rates

    def predict_inventory(
        self,
        resource: str,
        current_inventory: int,
        days_ahead: int,
        unlocked_shops: list[str] | tuple[str, ...],
        *,
        current_day: int = 0,
    ) -> int:
        """Predict inventory after complete future days with no player sales."""
        predicted = float(current_inventory)
        for offset in range(max(0, days_ahead)):
            rates = self.daily_drain_rates(
                unlocked_shops,
                current_day=current_day + offset,
            )
            predicted -= rates.get(resource, 0.0)
        return max(1, int(predicted))

    def predict_price(
        self,
        resource: str,
        current_inventory: int,
        days_ahead: int,
        unlocked_shops: list[str] | tuple[str, ...],
        *,
        current_day: int = 0,
    ) -> float:
        if self._market is None:
            return 0.0
        predicted = self.predict_inventory(
            resource,
            current_inventory,
            days_ahead,
            unlocked_shops,
            current_day=current_day,
        )
        return float(self._market.calculate_price(resource, predicted))

    def should_hold(
        self,
        resource: str,
        current_inventory: int,
        current_price: float,
        unlocked_shops: list[str] | tuple[str, ...],
        days_ahead: int = 3,
        hold_threshold: float = 1.15,
        *,
        current_day: int = 0,
    ) -> bool:
        predicted = self.predict_price(
            resource,
            current_inventory,
            days_ahead,
            unlocked_shops,
            current_day=current_day,
        )
        return predicted >= current_price * hold_threshold
