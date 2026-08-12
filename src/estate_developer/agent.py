
"""
The-Greatest-Estate-Developer.

V1.2:
    Controlled three-cell wheat production.
"""

from __future__ import annotations

from typing import Any

from estate_developer.state.parser import ObservationParser
from estate_developer.actions.farmer import ReliableFarmer


class EstateDeveloperAgent:
    """V1.2 three-cell wheat agent."""

    CROP = "WHEAT"

    SEED_COST = 10

    MAX_ACTIVE_WHEAT = 3

    def __init__(self) -> None:
        self.parser = ObservationParser()
        self.farmer = ReliableFarmer()

    @classmethod
    def active_wheat_count(cls, state) -> int:

        count = 0

        for row in state.me.tiles:
            for tile in row:

                if (
                    isinstance(tile, dict)
                    and tile.get("kind") == "PLANT"
                    and tile.get("crop") == cls.CROP
                ):
                    count += 1

        return count

    @classmethod
    def carried_wheat(cls, state) -> int:

        if not state.private.inventories:
            return 0

        return int(
            state.private.inventories[0].get(
                cls.CROP,
                0,
            )
        )

    @classmethod
    def shed_wheat(cls, state) -> int:

        return int(
            state.private.shed.get(
                cls.CROP,
                0,
            )
        )

    def step(
        self,
        obs: dict[str, Any],
    ) -> dict[str, Any]:

        state = self.parser.parse(obs)

        farmer_action = self.farmer.decide(
            state
        )

        active_wheat = self.active_wheat_count(
            state
        )

        carried_wheat = self.carried_wheat(
            state
        )

        shed_wheat = self.shed_wheat(
            state
        )

        seed_count = int(
            state.private.seeds.get(
                self.CROP,
                0,
            )
        )

        market_orders = []

        # ----------------------------------------------------
        # SELL EVERYTHING CURRENTLY IN SHED
        # ----------------------------------------------------

        if shed_wheat > 0:
            market_orders.append(
                [
                    "SELL",
                    self.CROP,
                    shed_wheat,
                ]
            )

        # ----------------------------------------------------
        # BUY SEED ONLY IF THERE IS PRODUCTION CAPACITY
        # ----------------------------------------------------

        if (
            active_wheat < self.MAX_ACTIVE_WHEAT
            and seed_count == 0
            and carried_wheat == 0
            and state.me.money >= self.SEED_COST
        ):
            market_orders.append(
                [
                    "BUY_SEED",
                    self.CROP,
                    1,
                ]
            )

        return {
            "farmer": farmer_action,
            "hands": [],
            "market": market_orders,
        }


_agent = EstateDeveloperAgent()


def agent(
    obs: dict[str, Any],
) -> dict[str, Any]:
    """Kaggriculture entry point."""

    return _agent.step(obs)
