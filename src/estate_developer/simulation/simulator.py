"""
V11-backed stateful simulator.

Preserves the existing Simulator API while routing rollouts
through the reference-faithful V11 transition engine.
"""

from __future__ import annotations

from typing import Any

from estate_developer.simulation.state_copy import (
    copy_observation,
)

from estate_developer.simulation.simulation_context import (
    SimulationContext,
)

from estate_developer.simulation.v11_transition import (
    step_state,
)

from estate_developer.state.parser import (
    ObservationState,
)


class Simulator:
    """
    Stateful V11 simulation interface.

    Usage:

        sim = Simulator(initial_state)
        sim.step(action_dict)
        print(sim.state.me.money)
    """

    def __init__(
        self,
        initial_state: ObservationState,
        *,
        context: SimulationContext | None = None,
    ) -> None:

        # Never mutate caller state.
        self.state: ObservationState = (
            copy_observation(
                initial_state
            )
        )

        if context is not None:

            # Caller explicitly supplied the full context.
            self.context = context

        else:

            # For online planning, use the observed board size.
            # The hidden Kaggle seed remains unknown.
            board_size = len(
                self.state.me.tiles
            )

            self.context = SimulationContext(
                seed=None,
                board_size=board_size,
            )

    def step(
        self,
        action: dict[str, Any],
    ) -> ObservationState:
        """
        Apply exactly one V11 transition.
        """

        self.state = step_state(
            self.state,
            action,
            context=self.context,
        )

        return self.state
