
"""
The-Greatest-Estate-Developer.

V2.12 Dynamic Economic Production Agent.

V2 chooses:
    what should occupy a free production slot?

V1.4 scheduler/executor still determines:
    how should the farmer execute it?

Existing healthy crops are never replaced.
"""

from __future__ import annotations

from typing import Any

from estate_developer.state.parser import (
    ObservationParser,
)

from estate_developer.planning.generator import (
    TaskGenerator,
)

from estate_developer.planning.scheduler import (
    TaskScheduler,
)


class EstateDeveloperAgent:

    MAX_PRODUCTION_SLOTS = 3

    CANDIDATE_CROPS = (
        "WHEAT",
        "CARROT",
        "MELON",
    )

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
        # Generate dynamic tasks.
        # ----------------------------------------------------

        tasks = self.generator.generate(
            state,
            max_active_wheat=self.MAX_PRODUCTION_SLOTS,
        )

        # ----------------------------------------------------
        # Select highest-value executable task.
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
        # Market orders.
        # ----------------------------------------------------

        market_orders = []

        # ----------------------------------------------------
        # Economic seed purchase.
        # ----------------------------------------------------

        if selected.task_type.value == "BUY_SEED":

            if selected.crop is not None:

                market_orders.append(
                    [
                        "BUY_SEED",
                        selected.crop,
                        max(
                            1,
                            selected.quantity,
                        ),
                    ]
                )

        # ----------------------------------------------------
        # Sell completed inventory already in shed.
        #
        # Selling happens separately from the farmer action.
        # ----------------------------------------------------

        for crop in self.CANDIDATE_CROPS:

            quantity = int(
                state.private.shed.get(
                    crop,
                    0,
                )
            )

            if quantity > 0:

                market_orders.append(
                    [
                        "SELL",
                        crop,
                        quantity,
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
