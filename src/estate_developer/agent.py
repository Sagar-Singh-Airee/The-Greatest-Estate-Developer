
"""
The-Greatest-Estate-Developer.

V1.3.1:
    Planner-driven three-cell wheat executor.
"""

from __future__ import annotations

from typing import Any

from estate_developer.state.parser import ObservationParser
from estate_developer.planning.generator import TaskGenerator
from estate_developer.planning.scheduler import TaskScheduler


class EstateDeveloperAgent:

    CROP = "WHEAT"

    MAX_ACTIVE_WHEAT = 3

    def __init__(self):

        self.parser = ObservationParser()

        self.generator = TaskGenerator()

        self.scheduler = TaskScheduler()

    def step(
        self,
        obs: dict[str, Any],
    ) -> dict[str, Any]:

        state = self.parser.parse(obs)

        # -----------------------------------------------
        # Generate tasks
        # -----------------------------------------------

        tasks = self.generator.generate(
            state,
            max_active_wheat=self.MAX_ACTIVE_WHEAT,
        )

        # -----------------------------------------------
        # Select highest priority task
        # -----------------------------------------------

        selected = self.scheduler.choose(
            tasks
        )

        # -----------------------------------------------
        # Farmer operation
        # -----------------------------------------------

        farmer_action = self.scheduler.farmer_action(
            selected,
            state,
        )

        # -----------------------------------------------
        # Market operation
        # -----------------------------------------------

        market_orders = []

        if selected.task_type.value == "BUY_SEED":

            market_orders.append(
                [
                    "BUY_SEED",
                    self.CROP,
                    1,
                ]
            )

        elif selected.task_type.value == "PLACE":

            # Selling will happen on a later observation
            # once the wheat is actually in the shed.
            pass

        # -----------------------------------------------
        # Also sell wheat currently in shed.
        #
        # This remains safe because selling is independent
        # of farmer movement and does not create another
        # farmer task.
        # -----------------------------------------------

        shed_wheat = int(
            state.private.shed.get(
                self.CROP,
                0,
            )
        )

        if shed_wheat > 0:

            market_orders.append(
                [
                    "SELL",
                    self.CROP,
                    shed_wheat,
                ]
            )

        return {
            "farmer": farmer_action,
            "hands": [],
            "market": market_orders[:10],
        }


_agent = EstateDeveloperAgent()


def agent(
    obs: dict[str, Any],
) -> dict[str, Any]:

    return _agent.step(obs)
