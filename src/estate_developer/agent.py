
"""
The-Greatest-Estate-Developer.

V1.4:
    Global task scheduler with lightweight value awareness.

The architecture remains:
    observation
        ↓
    parser
        ↓
    task generation
        ↓
    task scoring
        ↓
    execution
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

        # ----------------------------------------------------
        # Generate all currently available tasks.
        # ----------------------------------------------------

        tasks = self.generator.generate(
            state,
            max_active_wheat=self.MAX_ACTIVE_WHEAT,
        )

        # ----------------------------------------------------
        # Select using V1.4 value-aware scoring.
        # ----------------------------------------------------

        selected = self.scheduler.choose(
            tasks,
            state,
        )

        # ----------------------------------------------------
        # Farmer action.
        # ----------------------------------------------------

        farmer_action = self.scheduler.farmer_action(
            selected,
            state,
        )

        # ----------------------------------------------------
        # Market actions.
        # ----------------------------------------------------

        market_orders = []

        if selected.task_type.value == "BUY_SEED":

            market_orders.append(
                [
                    "BUY_SEED",
                    self.CROP,
                    1,
                ]
            )

        # Sell wheat once it is actually in the shed.
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
