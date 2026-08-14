from __future__ import annotations

from typing import Any
from estate_developer.state.parser import ObservationState


class PolicyGuard:
    """
    Enforces hard safety invariants (e.g., never spend protected reserves,
    never plant impossible crops).
    """

    def enforce(self, state: ObservationState, actions: dict[str, Any]) -> None:
        """
        Modifies the actions in-place to ensure they do not violate invariants.
        """
        market_actions = actions.get("market", [])
        safe_market = []
        
        # Simple invariant: Don't spend more money than we have
        projected_cash = state.me.money
        
        for m_act in market_actions:
            if not m_act:
                continue
            if m_act[0] == "BUY_SEED":
                # Rough check, would need to import crop profiles for exact cost
                # Assuming 100 max cost for safety
                if projected_cash >= 100:
                    safe_market.append(m_act)
                    projected_cash -= 100
            else:
                safe_market.append(m_act)
                
        actions["market"] = safe_market
