from __future__ import annotations

from typing import Any
from estate_developer.state.parser import ObservationState
from estate_developer.simulation.simulator import Simulator


def rollout_plan(initial_state: ObservationState, plan: list[dict[str, Any]]) -> ObservationState:
    """
    Executes a single forward rollout of a given plan using the deterministic simulator.
    """
    sim = Simulator(initial_state)
    return sim.simulate_plan(plan)


def evaluate_terminal_cash(initial_state: ObservationState, plan: list[dict[str, Any]]) -> float:
    """
    Rolls out a plan and returns the terminal cash delta (ΔTerminalValue).
    """
    final_state = rollout_plan(initial_state, plan)
    
    # Simple terminal value: Cash + Value of Shed + Value of planted crops
    # To properly compute this, we should have a `terminal_value.py`.
    # For now, we return just the cash delta.
    return final_state.me.money - initial_state.me.money
