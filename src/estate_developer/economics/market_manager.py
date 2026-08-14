from __future__ import annotations
import math
from typing import Any, TYPE_CHECKING
from estate_developer.economics.town_forecaster import TownDemandForecaster
if TYPE_CHECKING:
    from estate_developer.state.parser import ObservationState
    from estate_developer.opponent.opponent_model import OpponentModel

class MarketManager:
    """
    Tracks and predicts market prices for optimal selling.
    Integrates town demand forecasting and opponent pressure.
    """
    
    I0 = 10000
    
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

        shed_count = sum(v for v in shed.values() if isinstance(v, (int, float)))
        needs_space = shed_count > 80

        for resource, quantity in shed.items():
            if not isinstance(quantity, (int, float)) or quantity <= 0:
                continue

            current_inv = int(market_inv.get(resource, self.I0))
            current_price = float(market_prices.get(resource, self.calculate_price(resource, current_inv)))
            base_price = self.MARKET_PARAMS.get(resource, {}).get("base", 0)

            # --- Predatory Front-Running ---
            # If the opponent is about to sell the same crop, dump everything NOW
            # to crash the price for them, overriding any hold logic.
            is_opp_dominant = (opp_dominant == resource)
            sell_qty = int(quantity)
            
            if is_opp_dominant:
                orders.append(["SELL", resource, sell_qty])
                continue

            # --- Hold logic: will price rise significantly in 3 days? ---
            should_hold = (
                not needs_space
                and forecaster.should_hold(
                    resource,
                    current_inv,
                    current_price,
                    unlocked_shops,
                    days_ahead=3,
                    hold_threshold=1.15,
                )
            )

            if should_hold:
                continue

            # Sell if price is near or above base, or we need space
            if current_price >= base_price * 0.9 or needs_space:
                orders.append(["SELL", resource, sell_qty])

        return orders
