from __future__ import annotations

from typing import Any

from estate_developer.simulation.reference_rules import (
    ANIMALS,
    CROPS,
    FARM_HAND_COST_MULT,
    LAND_PRICES,
)
from estate_developer.state.parser import ObservationState


def _hire_cost(hires_today: int) -> int:
    a, b = 1, 1
    for _ in range(max(0, hires_today)):
        a, b = b, a + b
    return FARM_HAND_COST_MULT * a


class PolicyGuard:
    """Validate an action queue against the actual market execution order."""

    def enforce(self, state: ObservationState, actions: dict[str, Any]) -> None:
        safe_market: list[list[Any]] = []
        projected_cash = float(state.me.money)
        projected_hires = int(state.me.hires_today)
        next_land = max(0, len(state.me.unlocked_quadrants) - 1)

        for raw_order in actions.get("market", []):
            if not isinstance(raw_order, list) or not raw_order:
                continue
            order = list(raw_order)
            op = order[0]

            # Sells are deliberately placed before investments.  Add a modest
            # discount for price impact, which still lets realized proceeds
            # fund a seed/land purchase in the same market phase.
            if op == "SELL":
                if len(order) < 3:
                    continue
                item = str(order[1])
                if item == "FERTILIZER" or item not in state.market.inventory:
                    continue
                quantity = max(0, min(int(order[2]), state.private.shed.get(item, 0)))
                if quantity <= 0:
                    continue
                unit_price = float(state.market.prices.get(item, 1))
                projected_cash += quantity * max(1.0, unit_price * 0.90)
                safe_market.append(["SELL", item, quantity])
                continue

            if op == "BUY_SEED":
                if len(order) < 3 or str(order[1]) not in CROPS:
                    continue
                crop = str(order[1])
                cost = int(CROPS[crop]["seed"])
                quantity = min(max(0, int(order[2])), int(projected_cash // cost))
                if quantity > 0:
                    safe_market.append(["BUY_SEED", crop, quantity])
                    projected_cash -= quantity * cost
                continue

            if op == "BUY_PRODUCT":
                if len(order) < 3 or str(order[1]) not in state.market.inventory:
                    continue
                item = str(order[1])
                cost = max(1, int(state.market.prices.get(item, 1)))
                quantity = min(max(0, int(order[2])), int(projected_cash // cost))
                if quantity > 0:
                    safe_market.append(["BUY_PRODUCT", item, quantity])
                    projected_cash -= quantity * cost
                continue

            if op == "BUY_ANIMAL":
                if len(order) < 3 or str(order[1]) not in ANIMALS:
                    continue
                animal = str(order[1])
                cost = int(ANIMALS[animal]["cost"])
                quantity = min(max(0, int(order[2])), int(projected_cash // cost))
                if quantity > 0:
                    safe_market.append(["BUY_ANIMAL", animal, quantity])
                    projected_cash -= quantity * cost
                continue

            if op == "HIRE":
                cost = _hire_cost(projected_hires)
                if projected_cash >= cost:
                    safe_market.append(["HIRE"])
                    projected_cash -= cost
                    projected_hires += 1
                continue

            if op == "BUY_LAND":
                if next_land < len(LAND_PRICES):
                    cost = LAND_PRICES[next_land]
                    if projected_cash >= cost:
                        safe_market.append(["BUY_LAND"])
                        projected_cash -= cost
                        next_land += 1
                continue

        actions["market"] = safe_market
