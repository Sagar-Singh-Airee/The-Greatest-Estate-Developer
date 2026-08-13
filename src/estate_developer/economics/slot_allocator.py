
"""
V2.11 Production Slot Allocator.

The allocator decides ONLY what should occupy a FREE
production slot.

It never replaces an existing healthy crop.

Initial candidate set:
    WHEAT
    CARROT
    MELON

Reason:
    These are the one-time crops for which our current
    production-batch model is sufficiently well defined.

The allocator considers:

    - current market inventory
    - current market price
    - seed cost
    - realized batch revenue
    - tile occupancy
    - remaining season

This is still an economic decision layer.
It does not execute farmer actions.
"""

from __future__ import annotations

from dataclasses import dataclass

from estate_developer.economics.crops import (
    CROP_PROFILES,
)

from estate_developer.economics.market import (
    simulate_sale,
)

from estate_developer.planning.production_capacity import (
    discover_production_tiles,
    count_active_production,
)


@dataclass(frozen=True)
class SlotCandidate:
    """Economic evaluation for one free production slot."""

    crop: str

    batch_size: int

    market_inventory: int

    starting_price: float

    ending_price: float

    realized_revenue: float

    seed_cost: float

    contribution: float

    production_days: int

    remaining_days_after_harvest: int

    contribution_per_tile_day: float

    season_feasible: bool


class ProductionSlotAllocator:
    """
    Allocate one currently-free production slot.
    """

    # --------------------------------------------------------
    # Three-slot capacity discovered empirically.
    # --------------------------------------------------------

    MAX_PRODUCTION_SLOTS = 5

    # --------------------------------------------------------
    # Current validated one-time candidates.
    # --------------------------------------------------------

    BATCH_SIZES = {
        "WHEAT": 4,
        "CARROT": 3,
        "MELON": 6,
    }

    ONE_TIME_CROPS = (
        "WHEAT",
        "CARROT",
        "MELON",
    )

    SEASON_DAYS = 30

    # Minimum number of days reserved for execution
    # overhead after the theoretical crop completion date.
    SEASON_BUFFER_DAYS = 0

    def count_active_slots(
        self,
        state,
    ) -> int:
        """
        Count active one-time production crops across
        the dynamically discovered farm.

        Only the allocator's validated one-time crop set
        counts toward production utilization.
        """

        count = 0

        for row in state.me.tiles:

            for tile in row:

                if not isinstance(
                    tile,
                    dict,
                ):
                    continue

                if tile.get(
                    "kind"
                ) != "PLANT":
                    continue

                if tile.get(
                    "crop"
                ) not in self.ONE_TIME_CROPS:
                    continue

                count += 1

        return count

    def free_slot_count(
        self,
        state,
    ) -> int:
        """
        Return free production capacity.

        Physical capacity is discovered dynamically from
        unlocked empty farm tiles.

        MAX_PRODUCTION_SLOTS remains the economic utilization
        ceiling so V2.39's five-slot policy is preserved.
        """

        active = self.count_active_slots(
            state
        )

        physical_free = len(
            discover_production_tiles(
                state.me.tiles
            )
        )

        policy_free = max(
            0,
            self.MAX_PRODUCTION_SLOTS - active,
        )

        return min(
            physical_free,
            policy_free,
        )

    def evaluate(
        self,
        crop: str,
        state,
    ) -> SlotCandidate:
        """
        Evaluate one candidate crop for a currently free slot.
        """

        if crop not in self.ONE_TIME_CROPS:
            raise ValueError(
                f"{crop} is not a V2.11 candidate."
            )

        profile = CROP_PROFILES[crop]

        batch_size = self.BATCH_SIZES[crop]

        market_inventory = int(
            state.market.inventory[crop]
        )

        market_result = simulate_sale(
            crop,
            starting_inventory=market_inventory,
            quantity=batch_size,
        )

        production_days = (
            profile.max_yield_day
        )

        current_day = int(
            state.day
        )

        theoretical_finish_day = (
            current_day
            + production_days
        )

        remaining_days_after_harvest = (
            self.SEASON_DAYS
            - theoretical_finish_day
        )

        season_feasible = (
            theoretical_finish_day
            + self.SEASON_BUFFER_DAYS
            <= self.SEASON_DAYS
        )

        contribution = (
            market_result.realized_revenue
            - profile.seed_cost
        )

        tile_days = max(
            1,
            production_days,
        )

        contribution_per_tile_day = (
            contribution
            / tile_days
        )

        return SlotCandidate(
            crop=crop,
            batch_size=batch_size,
            market_inventory=market_inventory,
            starting_price=(
                market_result.starting_price
            ),
            ending_price=(
                market_result.ending_price
            ),
            realized_revenue=(
                market_result.realized_revenue
            ),
            seed_cost=float(
                profile.seed_cost
            ),
            contribution=contribution,
            production_days=production_days,
            remaining_days_after_harvest=(
                remaining_days_after_harvest
            ),
            contribution_per_tile_day=(
                contribution_per_tile_day
            ),
            season_feasible=season_feasible,
        )

    # ========================================================
    # RANKING
    # ========================================================

    def rank(
        self,
        state,
    ) -> list[SlotCandidate]:
        """
        Rank feasible candidates by marginal contribution
        per occupied tile-day.
        """

        results = []

        for crop in self.ONE_TIME_CROPS:

            candidate = self.evaluate(
                crop,
                state,
            )

            if candidate.season_feasible:
                results.append(
                    candidate
                )

        results.sort(
            key=lambda item: (
                item.contribution_per_tile_day,
                item.contribution,
            ),
            reverse=True,
        )

        return results

    def best(
        self,
        state,
    ) -> SlotCandidate | None:
        """
        Return the best feasible crop for a free slot.

        Returns None if:
            - no slot is available
            - no crop is season-feasible
        """

        if self.free_slot_count(state) <= 0:
            return None

        ranked = self.rank(
            state
        )

        if not ranked:
            return None

        return ranked[0]

    # ========================================================
    # DEBUG SUMMARY
    # ========================================================

    def explain(
        self,
        state,
    ) -> list[dict]:
        """
        Return a simple, serializable explanation of the
        allocator's ranking.
        """

        rows = []

        for candidate in self.rank(state):

            rows.append({
                "crop": candidate.crop,
                "batch": candidate.batch_size,
                "market_inventory": (
                    candidate.market_inventory
                ),
                "start_price": (
                    candidate.starting_price
                ),
                "end_price": (
                    candidate.ending_price
                ),
                "revenue": (
                    candidate.realized_revenue
                ),
                "seed_cost": (
                    candidate.seed_cost
                ),
                "contribution": (
                    candidate.contribution
                ),
                "days": (
                    candidate.production_days
                ),
                "tile_day": (
                    candidate.contribution_per_tile_day
                ),
                "season_feasible": (
                    candidate.season_feasible
                ),
            })

        return rows

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _tile_at(
        tiles,
        x: int,
        y: int,
    ):

        if y < 0 or y >= len(tiles):
            return None

        if x < 0 or x >= len(tiles[y]):
            return None

        return tiles[y][x]
