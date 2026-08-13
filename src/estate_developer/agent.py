
"""
The-Greatest-Estate-Developer.

V2.12 Dynamic Economic Production Agent.

V4.68:
    Adds one empirically validated V4 production override.

Architecture:

    Observation
        ↓
    V4 validated opportunity guard
        ↓
        ├── approved → BUY_SEED WHEAT
        │
        └── otherwise → unchanged V2 scheduler
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

from estate_developer.planning.v4_override import (
    V4ValidatedOverride,
)


class EstateDeveloperAgent:

    MAX_PRODUCTION_SLOTS = 9

    CANDIDATE_CROPS = (
        "WHEAT",
        "CARROT",
        "MELON",
    )

    def __init__(self):

        self.parser = ObservationParser()

        self.generator = TaskGenerator()

        self.scheduler = TaskScheduler()

        # ----------------------------------------------------
        # V4 validated override.
        #
        # V2 remains the fallback controller.
        # ----------------------------------------------------

        self.v4_override = (
            V4ValidatedOverride()
        )

    def step(
        self,
        obs: dict[str, Any],
    ) -> dict[str, Any]:

        # ----------------------------------------------------
        # V4 VALIDATED OVERRIDE
        # ----------------------------------------------------

        v4_crop = (
            self.v4_override.observe(
                obs
            )
        )

        if v4_crop == "WHEAT":

            return {
                "farmer": [
                    "PASS"
                ],
                "hands": [],
                "market": [
                    [
                        "BUY_SEED",
                        "WHEAT",
                        1,
                    ]
                ],
            }

        # ----------------------------------------------------
        # NORMAL V2 PATH — UNCHANGED
        # ----------------------------------------------------

        state = self.parser.parse(
            obs
        )

        tasks = self.generator.generate(
            state,
            max_active_wheat=(
                self.MAX_PRODUCTION_SLOTS
            ),
        )

        selected = self.scheduler.choose(
            tasks,
            state,
        )

        farmer_action = (
            self.scheduler.farmer_action(
                selected,
                state,
            )
        )

        market_orders = []

        if (
            selected.task_type.value
            == "BUY_SEED"
        ):

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

        # V2 selling remains untouched.

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

    return _agent.step(
        obs
    )
