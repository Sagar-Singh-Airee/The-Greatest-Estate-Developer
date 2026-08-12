
"""
V2.7 Shadow Crop Selector.

IMPORTANT:
    This module does NOT control the agent.

It observes the real state and answers:

    "If a production slot became available right now,
     what crop would be economically attractive?"

The real V1.4 executor continues farming wheat.

The selector considers:

    1. Current market inventory
    2. Realized revenue for the next production batch
    3. Seed cost
    4. Tile occupancy time
    5. Marginal contribution per tile-day

No market orders are generated here.
"""

from __future__ import annotations

from dataclasses import dataclass

from estate_developer.economics.crops import (
    CROP_PROFILES,
)
from estate_developer.economics.market import (
    simulate_sale,
)


@dataclass(frozen=True)
class ShadowCandidate:
    """Economic evaluation of one possible next crop batch."""

    crop: str

    batch_size: int

    market_inventory: int

    starting_price: float

    ending_price: float

    realized_revenue: float

    seed_cost: float

    contribution: float

    tile_days: int

    contribution_per_tile_day: float


class ShadowCropSelector:
    """
    Recommend the next crop without changing agent behavior.
    """

    BATCH_SIZES = {
        "WHEAT": 4,
        "CARROT": 3,
        "TOMATO": 4,
        "STRAWBERRY": 4,
        "MELON": 6,
    }

    def evaluate_crop(
        self,
        crop: str,
        state,
    ) -> ShadowCandidate:
        """
        Evaluate one production batch using the CURRENT
        observed market inventory.
        """

        if crop not in CROP_PROFILES:
            raise ValueError(
                f"Unknown crop: {crop}"
            )

        profile = CROP_PROFILES[crop]

        batch_size = self.BATCH_SIZES[crop]

        market_inventory = int(
            state.market.inventory.get(
                crop,
                profile.base_price,
            )
        )

        # simulate_sale accepts an actual starting market
        # inventory, so we can evaluate the next batch from
        # the current observed market state.
        sale = simulate_sale(
            crop,
            starting_inventory=market_inventory,
            quantity=batch_size,
        )

        contribution = (
            sale.realized_revenue
            - profile.seed_cost
        )

        tile_days = max(
            1,
            profile.max_yield_day,
        )

        contribution_per_tile_day = (
            contribution / tile_days
        )

        return ShadowCandidate(
            crop=crop,
            batch_size=batch_size,
            market_inventory=market_inventory,
            starting_price=sale.starting_price,
            ending_price=sale.ending_price,
            realized_revenue=sale.realized_revenue,
            seed_cost=float(
                profile.seed_cost
            ),
            contribution=contribution,
            tile_days=tile_days,
            contribution_per_tile_day=(
                contribution_per_tile_day
            ),
        )

    def rank(
        self,
        state,
    ) -> list[ShadowCandidate]:
        """Rank all crops by marginal contribution per tile-day."""

        results = []

        for crop in CROP_PROFILES:
            results.append(
                self.evaluate_crop(
                    crop,
                    state,
                )
            )

        results.sort(
            key=lambda result: (
                result.contribution_per_tile_day
            ),
            reverse=True,
        )

        return results

    def best(
        self,
        state,
    ) -> ShadowCandidate:
        """Return the current best shadow recommendation."""

        ranked = self.rank(state)

        if not ranked:
            raise RuntimeError(
                "No crops available for shadow evaluation."
            )

        return ranked[0]

    def compare_against_wheat(
        self,
        state,
    ) -> dict:
        """
        Compare every crop against the current wheat
        production baseline.
        """

        wheat = self.evaluate_crop(
            "WHEAT",
            state,
        )

        comparisons = {}

        for result in self.rank(state):

            comparisons[result.crop] = {
                "contribution_delta": (
                    result.contribution
                    - wheat.contribution
                ),
                "tile_day_delta": (
                    result.contribution_per_tile_day
                    - wheat.contribution_per_tile_day
                ),
                "beats_wheat": (
                    result.contribution_per_tile_day
                    > wheat.contribution_per_tile_day
                ),
            }

        return comparisons
