from __future__ import annotations
import math
from typing import Any, TYPE_CHECKING

from estate_developer.simulation.reference_rules import (
    MARKET_I0,
    MARKET_PARAMS as REFERENCE_MARKET_PARAMS,
    market_price,
    TURNS_PER_DAY,
)
from estate_developer.economics.price_forecaster import PriceForecaster
from estate_developer.opponent.sell_predictor import OpponentSellPredictor

if TYPE_CHECKING:
    from estate_developer.state.parser import ObservationState
    from estate_developer.opponent.opponent_model import OpponentModel


class MarketManager:
    """
    Tracks and predicts market prices for optimal selling and buying.
    Integrates town demand forecasting, opponent pressure, and arbitrage.

    V13: Uses PriceForecaster and OpponentSellPredictor for optimal timing.
    """

    I0 = MARKET_I0

    # Max units to buy per arbitrage opportunity per step.
    MAX_ARBITRAGE_BUY = 25

    # Minimum expected profit multiplier to trigger a buy (15% margin).
    ARBITRAGE_MIN_MARGIN = 1.15

    # Max fraction of current cash to spend on arbitrage in one step.
    ARBITRAGE_CASH_FRACTION = 0.40

    MARKET_PARAMS = REFERENCE_MARKET_PARAMS

    def _evaluate_func(self, func_name: str, x: float) -> float:
        if func_name == "linear":
            return x
        elif func_name == "sq":
            return x * x
        elif func_name == "sqrt":
            return math.sqrt(max(0, x))
        elif func_name == "log":
            return math.log(1 + max(0, x))
        elif func_name == "log10":
            return math.log10(1 + max(0, x))
        return x

    def get_optimal_buy_orders(
        self,
        state: "ObservationState",
        opponent_model: "OpponentModel | None" = None,
    ) -> list[list]:
        """
        Market Arbitrage Engine with improved price forecasting.
        """
        orders = []
        market_inv = state.market.inventory
        market_prices = state.market.prices
        current_money = state.me.money
        budget = current_money * self.ARBITRAGE_CASH_FRACTION

        unlocked_shops = getattr(
            getattr(state, "town", None), "unlocked_shops", []
        ) or []

        forecaster = PriceForecaster(state)

        # ---- Emergency wheat buy for animal feeding ----
        animal_count = sum(
            1
            for row in state.me.tiles
            for tile in row
            if isinstance(tile, dict)
            and tile.get("kind") in ("COOP", "PASTURE")
            and tile.get("animal")
        )
        if animal_count > 0:
            shed_wheat = int(state.private.shed.get("WHEAT", 0))
            if shed_wheat < animal_count * 3:  # less than 3 days of feed
                wheat_price = float(market_prices.get("WHEAT", 25))
                need = min(
                    animal_count * 6 - shed_wheat,
                    self.MAX_ARBITRAGE_BUY * 3,
                )
                cost = need * wheat_price
                if cost <= budget and cost <= current_money * 0.5:
                    orders.append(["BUY_PRODUCT", "WHEAT", int(need)])
                    budget -= cost

        # ---- Arbitrage: buy under-priced shop-demanded products ----
        from estate_developer.simulation.reference_rules import SHOPS

        demanded: set[str] = set()
        for shop in unlocked_shops:
            for product in SHOPS.get(shop, ()):
                demanded.add(product)

        for product in demanded:
            current_inv = int(market_inv.get(product, self.I0))
            current_price = float(market_prices.get(product, self.calculate_price(product, current_inv)))
            base_price = self.MARKET_PARAMS.get(product, {}).get("base", current_price)

            # Only buy when price is below base (surplus, cheap supply)
            if current_price >= base_price:
                continue

            # Predict price 3 days (72 steps) out using the full forecaster
            predicted_price = forecaster.forecast_price(
                product,
                steps_ahead=72,  # 3 days
                own_sales=None,
            )

            # Check minimum profit threshold
            if predicted_price < current_price * self.ARBITRAGE_MIN_MARGIN:
                continue

            # Don't hold more than 40 units of any one product
            shed_qty = int(state.private.shed.get(product, 0))
            if shed_qty >= 40:
                continue

            buy_qty = min(
                self.MAX_ARBITRAGE_BUY,
                int(budget // max(1, current_price)),
            )
            if buy_qty <= 0:
                continue

            cost = buy_qty * current_price
            if cost > current_money * 0.6:  # never spend more than 60% on one buy
                buy_qty = max(1, int(current_money * 0.6 / max(1, current_price)))
                cost = buy_qty * current_price

            if buy_qty > 0 and cost <= budget:
                orders.append(["BUY_PRODUCT", product, buy_qty])
                budget -= cost

        return orders

    def calculate_price(self, resource: str, inventory: int) -> int:
        if resource not in self.MARKET_PARAMS:
            return 1
        return market_price(resource, int(inventory))

    def get_optimal_sell_orders(
        self,
        state: "ObservationState",
        opponent_model: "OpponentModel | None" = None,
    ) -> list[list[Any]]:
        """
        Sell liquid inventory at optimal times using PriceForecaster and OpponentSellPredictor.

        V13: Intelligently times sales to maximize price while avoiding opponent sell days.
        """
        orders: list[list[Any]] = []
        shed = state.private.shed
        market_inv = state.market.inventory
        market_prices = state.market.prices
        current_day = int(state.day)

        shed_count = sum(
            value for value in shed.values()
            if isinstance(value, (int, float))
        )
        needs_space = shed_count >= 90
        days_remaining = max(0, 30 - current_day)
        animal_count = sum(
            1
            for row in state.me.tiles
            for tile in row
            if isinstance(tile, dict)
            and tile.get("kind") in ("COOP", "PASTURE")
            and tile.get("animal")
        )

        # ---- Early game: sell everything to fuel expansion ----
        if current_day < 5:
            for resource, quantity in shed.items():
                if (
                    resource not in self.MARKET_PARAMS
                    or resource == "FERTILIZER"
                    or not isinstance(quantity, (int, float))
                    or quantity <= 0
                ):
                    continue
                sell_qty = int(quantity)
                if resource == "WHEAT" and animal_count:
                    sell_qty = max(0, sell_qty - animal_count * 3)
                if sell_qty > 0:
                    orders.append(["SELL", resource, sell_qty])
            return orders

        # ---- Normal selling logic with forecasting ----
        forecaster = PriceForecaster(state)
        opponent_predictor = OpponentSellPredictor(state)
        opponent_sell_days = opponent_predictor.opponent_sell_windows(horizon_days=3)

        for resource, quantity in shed.items():
            if (
                resource not in self.MARKET_PARAMS
                or resource == "FERTILIZER"
                or not isinstance(quantity, (int, float))
                or quantity <= 0
            ):
                continue

            sell_qty = int(quantity)
            if resource == "WHEAT" and animal_count:
                sell_qty = max(0, sell_qty - animal_count * 3)
            if sell_qty <= 0:
                continue

            # If shed is too full, sell immediately
            if needs_space:
                orders.append(["SELL", resource, sell_qty])
                continue

            # Find optimal sell day within the next 3 days (72 steps)
            # We'll check sell prices if we sell now vs holding for 1,2,3 days.
            best_step = 0
            best_price = 0.0

            # Check 0, 1, 2, 3 days ahead
            for steps_ahead in [0, 24, 48, 72]:
                if steps_ahead == 0:
                    # Current price
                    price = float(market_prices.get(resource, self.calculate_price(resource, market_inv.get(resource, self.I0))))
                else:
                    # Forecast price assuming we sell this quantity at that time
                    price = forecaster.forecast_price(
                        resource,
                        steps_ahead=steps_ahead,
                        own_sales={resource: sell_qty},
                    )

                # If opponent is selling this product on the day we would sell,
                # penalize the price to avoid collision.
                sell_day = current_day + (steps_ahead // TURNS_PER_DAY)
                if resource in opponent_sell_days and sell_day in opponent_sell_days[resource]:
                    price *= 0.85  # 15% penalty for concurrent selling

                if price > best_price:
                    best_price = price
                    best_step = steps_ahead

            # If best price is significantly higher than current, hold
            current_price = float(market_prices.get(resource, self.calculate_price(resource, market_inv.get(resource, self.I0))))
            if best_step > 0 and best_price > current_price * 1.05:
                # Hold for better price (but only if we have enough room in shed)
                continue

            # Otherwise, sell now
            orders.append(["SELL", resource, sell_qty])

        return orders