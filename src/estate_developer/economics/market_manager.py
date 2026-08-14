from __future__ import annotations
import math
from typing import Any, TYPE_CHECKING
from estate_developer.economics.town_forecaster import TownDemandForecaster
if TYPE_CHECKING:
    from estate_developer.state.parser import ObservationState
    from estate_developer.opponent.opponent_model import OpponentModel

class MarketManager:
    """
    Tracks and predicts market prices for optimal selling and buying.
    Integrates town demand forecasting, opponent pressure, and arbitrage.
    """
    
    I0 = 10000

    # Max units to buy per arbitrage opportunity per step.
    MAX_ARBITRAGE_BUY = 10

    # Minimum expected profit multiplier to trigger a buy (30% margin).
    ARBITRAGE_MIN_MARGIN = 1.30

    # Max fraction of current cash to spend on arbitrage in one step.
    ARBITRAGE_CASH_FRACTION = 0.25
    
    MARKET_PARAMS = {
        "WHEAT": {"base": 25, "T": 400, "below_func": "sqrt", "below_target": 0.8, "above_func": "log", "above_target": 0.2},
        "CARROT": {"base": 35, "T": 450, "below_func": "log", "below_target": 0.2, "above_func": "sqrt", "above_target": 0.7},
        "TOMATO": {"base": 60, "T": 200, "below_func": "linear", "below_target": 0.4, "above_func": "sqrt", "above_target": 0.6},
        "STRAWBERRY": {"base": 120, "T": 100, "below_func": "sqrt", "below_target": 0.7, "above_func": "linear", "above_target": 1.6},
        "MELON": {"base": 250, "T": 300, "below_func": "log", "below_target": 0.2, "above_func": "sq", "above_target": 3.6},
        "EGG": {"base": 50, "T": 332, "below_func": "linear", "below_target": 0.4, "above_func": "log", "above_target": 0.2},
        "MILK": {"base": 160, "T": 122, "below_func": "sqrt", "below_target": 0.6, "above_func": "linear", "above_target": 1.6},
        "WOOL": {"base": 200, "T": 105, "below_func": "log", "below_target": 0.2, "above_func": "sq", "above_target": 3.2},
        "FERTILIZER": {"base": 100, "T": 200, "below_func": "linear", "below_target": 0.4, "above_func": "linear", "above_target": 0.4},
    }

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
            and "animal" in tile
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
                product, current_inv, days_ahead=2, unlocked_shops=list(unlocked_shops)
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
            
        params = self.MARKET_PARAMS[resource]
        base = params["base"]
        T = params["T"]
        
        if inventory == self.I0:
            return base
            
        diff = abs(inventory - self.I0)
        
        if inventory < self.I0:
            sign = 1
            func = params["below_func"]
            target = params["below_target"]
        else:
            sign = -1
            func = params["above_func"]
            target = params["above_target"]
            
        amp = (target * base) / self._evaluate_func(func, T)
        
        price = base + sign * amp * self._evaluate_func(func, diff)
        
        return max(1, round(price))

    def get_optimal_sell_orders(
        self,
        state: "ObservationState",
        opponent_model: "OpponentModel | None" = None,
    ) -> list[list[Any]]:
        """
        Determines which items in the shed should be sold right now.
        Uses town demand forecasting to hold when prices are rising,
        and stagers selling when the opponent is likely selling the same crop.
        """
        orders = []
        shed = state.private.shed
        market_inv = state.market.inventory
        market_prices = state.market.prices
        unlocked_shops = getattr(
            getattr(state, "town", None), "unlocked_shops", []
        ) or []

        forecaster = TownDemandForecaster(market_manager=self)

        # Opponent dominant crop for stagger logic
        opp_dominant = None
        if opponent_model is not None:
            opp_dominant = opponent_model.dominant_crop()

        # Products that benefit enormously from supply-bombing:
        # WOOL uses sq price curve (price explodes when inventory < I0)
        # MELON uses sq curve on above side with high above_target
        # Hold these until town shops drain market below spike threshold.
        SPIKE_HOLD_PRODUCTS = {"WOOL", "MELON"}
        SPIKE_THRESHOLD = 9500  # hold until market inventory < this

        shed_count = sum(v for v in shed.values() if isinstance(v, (int, float)))
        needs_space = shed_count >= 70  # was 80; tighter to avoid gridlock

        for resource, quantity in shed.items():
            if not isinstance(quantity, (int, float)) or quantity <= 0:
                continue

            current_inv = int(market_inv.get(resource, self.I0))
            current_price = float(market_prices.get(resource, self.calculate_price(resource, current_inv)))
            base_price = self.MARKET_PARAMS.get(resource, {}).get("base", 0)

            # --- Hard override: shed full, sell everything immediately ---
            if needs_space:
                orders.append(["SELL", resource, int(quantity)])
                continue

            # --- Predatory Front-Running ---
            # If the opponent is about to sell the same crop, dump everything NOW
            # to crash the price for them, overriding any hold logic.
            is_opp_dominant = (opp_dominant == resource)
            sell_qty = int(quantity)
            
            if is_opp_dominant:
                orders.append(["SELL", resource, sell_qty])
                continue

            # --- Supply Bombing: hold WOOL/MELON until inventory drains ---
            if resource in SPIKE_HOLD_PRODUCTS:
                if current_inv >= SPIKE_THRESHOLD:
                    # Market still flooded, hold and let shops drain it
                    continue
                # Market has drained below threshold — DUMP everything for spike price
                orders.append(["SELL", resource, sell_qty])
                continue

            # --- Hold logic: will price rise significantly in 3 days? ---
            should_hold = forecaster.should_hold(
                resource,
                current_inv,
                current_price,
                unlocked_shops,
                days_ahead=3,
                hold_threshold=1.15,
            )

            if should_hold:
                continue

            # Sell if price is near or above base
            if current_price >= base_price * 0.9:
                orders.append(["SELL", resource, sell_qty])

        return orders
