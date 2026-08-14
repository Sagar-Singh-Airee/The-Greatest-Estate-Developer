from __future__ import annotations

from typing import Any

from estate_developer.state.parser import ObservationState
from estate_developer.simulation.state_copy import copy_observation
from estate_developer.simulation.transition import apply_action, tick_environment


class Simulator:
    """
    Deterministic state transition simulator for evaluating plans.
    """

    def __init__(self, initial_state: ObservationState):
        """
        Initializes the simulator with a deep copy of the starting state.
        """
        self.state = copy_observation(initial_state)

    def step(self, actions: dict[str, Any]) -> None:
        """
        Applies a set of actions and advances the environment by one tick.
        """
        apply_action(self.state, actions)
        tick_environment(self.state)

    def simulate_plan(self, plan: list[dict[str, Any]]) -> ObservationState:
        """
        Simulates an entire sequence of actions and returns the final state.
        """
        for actions in plan:
            self.step(actions)
        return self.state
