"""
Simulator: thin wrapper around apply_action + tick_environment.
Provides a stateful step() interface for testing and rollouts.
"""
from __future__ import annotations

from typing import Any

from estate_developer.simulation.state_copy import copy_observation
from estate_developer.simulation.transition import apply_action, tick_environment
from estate_developer.state.parser import ObservationState


class Simulator:
    """
    A stateful simulation interface.

    Usage:
        sim = Simulator(initial_state)
        sim.step(action_dict)
        print(sim.state.me.money)
    """

    def __init__(self, initial_state: ObservationState) -> None:
        # Always work on a deep copy so we don't mutate caller's state.
        self.state: ObservationState = copy_observation(initial_state)

    def step(self, action: dict[str, Any]) -> ObservationState:
        """
        Apply `action` to the current state and advance one tick.
        Returns the resulting state.
        """
        apply_action(self.state, action)
        tick_environment(self.state)
        return self.state
