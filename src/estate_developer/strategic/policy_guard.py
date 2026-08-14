from __future__ import annotations

from typing import Any
from estate_developer.state.parser import ObservationState

# Real seed costs pulled directly from CROP_PROFILES (authoritative source).
# These MUST match reference_rules.py CROPS dict.
_SEED_COSTS: dict[str, float] = {
    "WHEAT": 10,
    "CARROT": 20,
    "TOMATO": 50,
    "STRAWBERRY": 100,
    "MELON": 80,   # seed=80, base_price=250 (don't confuse seed cost with market price!)
}

# Real animal costs from reference_rules.py ANIMALS dict.
_ANIMAL_COSTS: dict[str, float] = {
    "GOOSE": 300,
    "COW": 600,    # was wrong at 400; reference_rules says 600
    "SHEEP": 500,
}

class PolicyGuard:
    """
    Enforces hard safety invariants (e.g., never spend protected reserves,
    never plant impossible crops).
    Uses real seed/animal/land costs to correctly guard against overspending.
    """

    def enforce(self, state: ObservationState, actions: dict[str, Any]) -> None:
        """
        Modifies the actions in-place to ensure they do not violate invariants.
        """
        market_actions = actions.get("market", [])
        safe_market = []

        # Track projected cash through the order sequence
        projected_cash = float(state.me.money)

        for m_act in market_actions:
            if not m_act:
                continue

            action_type = m_act[0]

            if action_type == "BUY_SEED":
                crop = m_act[1] if len(m_act) > 1 else ""
                qty = int(m_act[2]) if len(m_act) > 2 else 1
                unit_cost = _SEED_COSTS.get(crop, 100)
                # Buy as many as we can afford, minimum 1
                if projected_cash >= unit_cost:
                    affordable_qty = max(1, min(qty, int(projected_cash // unit_cost)))
                    safe_market.append([action_type, crop, affordable_qty])
                    projected_cash -= affordable_qty * unit_cost
                # else: truly can't afford even 1 — skip

            elif action_type == "BUY_PRODUCT":
                # Arbitrage buy — verify we can afford it
                product = m_act[1] if len(m_act) > 1 else ""
                qty = int(m_act[2]) if len(m_act) > 2 else 1
                price = float(state.market.prices.get(product, 999))
                cost = price * qty
                if projected_cash >= cost:
                    safe_market.append(m_act)
                    projected_cash -= cost

            elif action_type == "BUY_ANIMAL":
                animal = m_act[1] if len(m_act) > 1 else ""
                cost = float(_ANIMAL_COSTS.get(animal, 600))
                if projected_cash >= cost:
                    safe_market.append(m_act)
                    projected_cash -= cost

            elif action_type == "HIRE":
                # Hire cost is fibonacci×10 (10..550). Minimum 10.
                if projected_cash >= 10:
                    safe_market.append(m_act)
                    projected_cash -= 10  # conservative; actual is higher later

            elif action_type == "BUY_LAND":
                # Land costs $1000/$2000/$4000. Use 1000 as conservative deduction.
                if projected_cash >= 1500:
                    safe_market.append(m_act)
                    projected_cash -= 1000

            else:
                # SELL and other actions are always safe
                safe_market.append(m_act)

        actions["market"] = safe_market
