from __future__ import annotations

class CapitalModel:
    """
    Models the shadow price of capital, incorporating liquidity value and optionality.
    """

    def __init__(self, base_cash: float):
        self.base_cash = base_cash

    def evaluate_investment(self, current_cash: float, cost: float, expected_return: float) -> float:
        """
        Evaluates an investment considering the opportunity cost of lost liquidity.
        """
        if current_cash < cost:
            return float('-inf')
            
        remaining_cash = current_cash - cost
        
        # Simple liquidity penalty: if remaining cash is low, penalize the investment
        liquidity_penalty = 0.0
        if remaining_cash < 100:
            liquidity_penalty = (100 - remaining_cash) * 0.5
            
        return expected_return - cost - liquidity_penalty
