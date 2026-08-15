"""
V13 Price Forecaster.

Predicts future prices for all products based on:
    - Town consumption schedule (center + shops)
    - Expected player sales (provided by the planner)
    - Current market inventory

This allows the agent to time sales for maximum revenue.
"""

from __future__ import annotations

from typing import Any

from estate_developer.simulation.reference_rules import (
    MARKET_PARAMS,
    TOWN_CENTER_DEMAND_SCHEDULE,
    TOWN_CENTER_PRODUCTS,
    TOWN_CENTER_SELL_INTERVAL,
    TOWN_SHOP_SELL_INTERVAL,
    TURNS_PER_DAY,
    market_price,
)
from estate_developer.state.parser import ObservationState


class PriceForecaster:
    """Predict future market prices over a horizon."""

    def __init__(self, state: ObservationState):
        self.state = state
        self.current_step = state.step
        self.current_day = state.day
        self.current_inventory = dict(state.market.inventory)

        # We'll simulate consumption without our own sales first.
        # External sales can be applied by calling `apply_sales()`.

    def simulate_consumption(self, steps: int) -> dict[str, list[int]]:
        """
        Simulate town consumption for `steps` future steps.
        Returns a dict product -> list of predicted inventory after each step.
        """
        # Start with a copy of current inventory
        inv = dict(self.current_inventory)
        inventories: dict[str, list[int]] = {p: [] for p in inv}

        for step_offset in range(1, steps + 1):
            step = self.current_step + step_offset
            day = step // TURNS_PER_DAY

            # Town shops consumption
            if step % TOWN_SHOP_SELL_INTERVAL == 0:
                for shop in self.state.town.unlocked_shops:
                    products = self._shop_products(shop)
                    multiplier = 2 if len(products) == 1 else 1
                    for item in products:
                        if item in inv:
                            inv[item] = max(0, inv[item] - multiplier)

            # Town center consumption
            if step % TOWN_CENTER_SELL_INTERVAL == 0:
                # Get daily demand multiplier
                demand = 1
                for threshold, mult in TOWN_CENTER_DEMAND_SCHEDULE:
                    if day >= threshold:
                        demand = mult
                        break
                for item in TOWN_CENTER_PRODUCTS:
                    if item in inv:
                        inv[item] = max(0, inv[item] - demand)

            # Record inventory after this step
            for p in inv:
                inventories[p].append(inv[p])

        return inventories

    def forecast_price(
        self,
        product: str,
        steps_ahead: int,
        own_sales: dict[str, int] | None = None,
    ) -> float:
        """
        Forecast price after `steps_ahead` steps, given optional own sales.
        own_sales: dict product -> total units to sell over the horizon.
        """
        if product not in MARKET_PARAMS:
            return 0.0

        # Start from current inventory
        inv = self.current_inventory.get(product, 10000)

        # Subtract own sales (assume they occur uniformly or at the end?)
        # For simplicity, we apply all sales immediately (conservative for price)
        if own_sales and product in own_sales:
            inv = max(0, inv - own_sales[product])

        # Simulate consumption
        for step_offset in range(1, steps_ahead + 1):
            step = self.current_step + step_offset
            day = step // TURNS_PER_DAY

            # Shops
            if step % TOWN_SHOP_SELL_INTERVAL == 0:
                for shop in self.state.town.unlocked_shops:
                    products = self._shop_products(shop)
                    multiplier = 2 if len(products) == 1 else 1
                    if product in products:
                        inv = max(0, inv - multiplier)

            # Town center
            if step % TOWN_CENTER_SELL_INTERVAL == 0:
                demand = 1
                for threshold, mult in TOWN_CENTER_DEMAND_SCHEDULE:
                    if day >= threshold:
                        demand = mult
                        break
                if product in TOWN_CENTER_PRODUCTS:
                    inv = max(0, inv - demand)

        # Calculate price at that inventory
        return float(market_price(product, int(inv)))

    def optimal_sell_window(
        self,
        product: str,
        quantity: int,
        horizon: int = 48,
    ) -> tuple[int, float]:
        """
        Find the best step within `horizon` to sell `quantity` units.
        Returns (best_step, expected_price_at_best_step).
        """
        best_price = 0.0
        best_step = 0

        # We'll check each step in the horizon
        for steps in range(1, horizon + 1):
            price = self.forecast_price(
                product,
                steps,
                own_sales={product: quantity},
            )
            if price > best_price:
                best_price = price
                best_step = steps

        return best_step, best_price

    @staticmethod
    def _shop_products(shop: str) -> tuple[str, ...]:
        from estate_developer.simulation.reference_rules import SHOPS
        return SHOPS.get(shop, ())