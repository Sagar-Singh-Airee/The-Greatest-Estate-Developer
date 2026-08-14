from __future__ import annotations
import math
from typing import Any, TYPE_CHECKING

from estate_developer.simulation.reference_rules import (
    MARKET_I0,
    MARKET_PARAMS as REFERENCE_MARKET_PARAMS,
    market_price,
)
from estate_developer.economics.town_forecaster import TownDemandForecaster
if TYPE_CHECKING:
    from estate_developer.state.parser import ObservationState
    from estate_developer.opponent.opponent_model import OpponentModel

class MarketManager:
    """
    Tracks and predicts market prices for optimal selling and buying.
    Integrates town demand forecasting, opponent pressure, and arbitrage.
    """
    
    I0 = MARKET_I0

    # Max units to buy per arbitrage opportunity per step.
    MAX_ARBITRAGE_BUY = 10

    # Minimum expected profit multiplier to trigger a buy (30% margin).
    ARBITRAGE_MIN_MARGIN = 1.30

    # Max fraction of current cash to spend on arbitrage in one step.
    ARBITRAGE_CASH_FRACTION = 0.25
    
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
        Market Arbitrage Engine.

        Identifies products that:
          1. Are demanded by currently unlocked Town Shops (guaranteed buyer).
          2. Are currently priced BELOW base price (market is oversupplied).
          3. Are predicted to rise above the buy price × ARBITRAGE_MIN_MARGIN
             within the next 2 days as shops drain supply.

        Generates BUY_PRODUCT orders when all three conditions are met.
        Also generates emergency WHEAT buys when animals need feeding and
        the shed wheat is critically low.
        """
        orders = []
        market_inv = state.market.inventory
        market_prices = state.market.prices
        current_money = state.me.money
        budget = current_money * self.ARBITRAGE_CASH_FRACTION

        unlocked_shops = getattr(
            getattr(state, "town", None), "unlocked_shops", []
        ) or []

        forecaster = TownDemandForecaster(market_manager=self)

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
            # If wheat in shed covers fewer than 3 days of feeding, emergency-buy
            if shed_wheat < animal_count * 3:
                wheat_price = float(market_prices.get("WHEAT", 25))
                need = min(
                    animal_count * 6 - shed_wheat,  # buffer up to 6 days
                    self.MAX_ARBITRAGE_BUY * 3,
                )
                cost = need * wheat_price
                if cost <= budget and cost <= current_money * 0.5:
                    orders.append(["BUY_PRODUCT", "WHEAT", int(need)])
                    budget -= cost

        # ---- Arbitrage: buy under-priced shop-demanded products ----
        from estate_developer.simulation.reference_rules import SHOPS

        # Collect all products demanded by currently unlocked shops
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

            # Predict price 2 days out as shops drain supply
            predicted_price = forecaster.predict_price(
                product,
                current_inv,
                days_ahead=2,
                unlocked_shops=unlocked_shops,
                current_day=int(state.day),
            )

            # Check minimum profit threshold
            if predicted_price < current_price * self.ARBITRAGE_MIN_MARGIN:
                continue

            # Don't hold more than 20 units of any one product
            shed_qty = int(state.private.shed.get(product, 0))
            if shed_qty >= 20:
                continue

            buy_qty = min(
                self.MAX_ARBITRAGE_BUY,
                int(budget // max(1, current_price)),
            )
            if buy_qty <= 0:
                continue

            cost = buy_qty * current_price
            if cost > current_money * 0.4:  # never spend more than 40% on one buy
                buy_qty = max(1, int(current_money * 0.4 / max(1, current_price)))
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
        """Sell liquid inventory while protecting operating inputs.

        There is no signal that an opponent will sell *this turn*, so crop
        dominance is not a valid reason to sacrifice our own price.  Likewise,
        the previous 9,500-inventory spike rule could hold MELON or WOOL for
        longer than the whole season.  We make only short, rule-based holds.
        """
        orders: list[list[Any]] = []
        shed = state.private.shed
        market_inv = state.market.inventory
        market_prices = state.market.prices
        unlocked_shops = state.town.unlocked_shops
        forecaster = TownDemandForecaster(market_manager=self)

        shed_count = sum(
            value for value in shed.values()
            if isinstance(value, (int, float))
        )
        needs_space = shed_count >= 85
        days_remaining = max(0, 30 - int(state.day))
        animal_count = sum(
            1
            for row in state.me.tiles
            for tile in row
            if isinstance(tile, dict)
            and tile.get("kind") in ("COOP", "PASTURE")
            and tile.get("animal")
        )

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
                # Three days of feed buys time for the pickup-and-care loop.
                sell_qty = max(0, sell_qty - animal_count * 3)
            if sell_qty <= 0:
                continue

            current_inv = int(market_inv.get(resource, self.I0))
            current_price = float(
                market_prices.get(
                    resource, self.calculate_price(resource, current_inv)
                )
            )
            base_price = float(self.MARKET_PARAMS[resource]["base"])

            if needs_space:
                orders.append(["SELL", resource, sell_qty])
                continue

            should_hold = forecaster.should_hold(
                resource,
                current_inv,
                current_price,
                unlocked_shops,
                days_ahead=min(2, days_remaining),
                hold_threshold=1.06,
                current_day=int(state.day),
            )
            if should_hold and days_remaining > 2:
                continue

            # Recycle working capital unless price is deeply distressed.
            if current_price >= base_price * 0.75 or days_remaining <= 2:
                orders.append(["SELL", resource, sell_qty])

        return orders
