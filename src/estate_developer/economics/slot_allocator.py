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

    V12: More aggressive early-game animal investment and higher slot cap.
    """

    # --------------------------------------------------------
    # Increased slot capacity for industrial farming
    # --------------------------------------------------------

    MAX_PRODUCTION_SLOTS = 30   # was 5

    # --------------------------------------------------------
    # Current validated one-time candidates.
    # --------------------------------------------------------

    BATCH_SIZES = {
        "WHEAT": 4,
        "CARROT": 3,
        "TOMATO": 4,
        "STRAWBERRY": 4,
        "MELON": 6,
    }

    ONE_TIME_CROPS = (
        "WHEAT",
        "CARROT",
        "TOMATO",
        "STRAWBERRY",
        "MELON",
    )

    # --------------------------------------------------------
    # Animal investment profiles (from Kaggriculture README).
    # --------------------------------------------------------

    ANIMAL_PROFILES = {
        "GOOSE": {
            "cost": 300,
            "setup_action": "BUILD_COOP",
            "first_yield_day": 4,
            "yield_interval": 1,
            "product": "EGG",
            "base_price": 50,
            "feed_cost_per_day": 25,
        },
        "COW": {
            "cost": 600,   # real cost from reference_rules.py
            "setup_action": "BUILD_PASTURE",
            "first_yield_day": 8,
            "yield_interval": 2,
            "product": "MILK",
            "base_price": 160,
            "feed_cost_per_day": 25,
        },
        "SHEEP": {
            "cost": 500,
            "setup_action": "BUILD_PASTURE",
            "first_yield_day": 6,
            "yield_interval": 3,
            "product": "WOOL",
            "base_price": 200,
            "feed_cost_per_day": 25,
        },
    }

    SEASON_DAYS = 30

    SEASON_BUFFER_DAYS = 0

    # Diversification caps — more permissive now
    DIVERSITY_CAP = 0.75          # was 0.60
    MELON_CAP = 0.50              # was 0.40

    # Early-game animal boost
    EARLY_ANIMAL_BONUS_DAYS = 3
    EARLY_ANIMAL_MULTIPLIER = 2.0

    def count_active_slots(
        self,
        state,
    ) -> int:
        """Count active one-time production crops."""

        count = 0

        for row in state.me.tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if tile.get("kind") != "PLANT":
                    continue
                if tile.get("crop") not in self.ONE_TIME_CROPS:
                    continue
                count += 1

        return count

    def free_slot_count(
        self,
        state,
    ) -> int:
        """Return free production capacity."""

        active = self.count_active_slots(state)
        physical_free = len(
            discover_production_tiles(state.me.tiles)
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
        """Evaluate one candidate crop for a currently free slot."""

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

    def evaluate_animal(
        self,
        animal: str,
        state,
    ) -> SlotCandidate | None:
        """
        Evaluate one animal as an investment for a free slot.
        Returns None if the season is too short to recoup investment.
        """
        profile = self.ANIMAL_PROFILES.get(animal)
        if not profile:
            return None

        current_day = int(state.day)
        first_yield_day = profile["first_yield_day"]
        setup_days = 2
        effective_first_yield = current_day + setup_days + first_yield_day

        if effective_first_yield >= self.SEASON_DAYS:
            return None

        producing_days = self.SEASON_DAYS - effective_first_yield
        yield_interval = profile["yield_interval"]
        num_yields = max(0, producing_days // yield_interval)

        if num_yields == 0:
            return None

        product = profile["product"]
        current_price = float(
            state.market.prices.get(product, profile["base_price"])
        )
        revenue = num_yields * current_price

        total_days_occupied = self.SEASON_DAYS - current_day
        feed_cost = total_days_occupied * profile["feed_cost_per_day"]
        total_cost = profile["cost"] + feed_cost

        contribution = revenue - total_cost
        tile_days = max(1, total_days_occupied)
        contribution_per_tile_day = contribution / tile_days

        # Early-game bonus: animals are worth more early
        if current_day < self.EARLY_ANIMAL_BONUS_DAYS:
            contribution_per_tile_day *= self.EARLY_ANIMAL_MULTIPLIER

        season_feasible = contribution > 0

        return SlotCandidate(
            crop=animal,
            batch_size=num_yields,
            market_inventory=int(
                state.market.inventory.get(product, 10000)
            ),
            starting_price=current_price,
            ending_price=current_price,
            realized_revenue=revenue,
            seed_cost=float(total_cost),
            contribution=contribution,
            production_days=total_days_occupied,
            remaining_days_after_harvest=0,
            contribution_per_tile_day=contribution_per_tile_day,
            season_feasible=season_feasible,
        )

    def rank(
        self,
        state,
    ) -> list[SlotCandidate]:
        """
        Rank all feasible candidates (crops AND animals) by
        contribution-per-tile-day.

        Includes market-saturation diversification and early-game
        animal bonus.
        """

        # Count active tiles per crop/animal for diversification
        crop_counts: dict[str, int] = {}
        total_active = 0
        for row in state.me.tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if tile.get("kind") == "PLANT":
                    c = tile.get("crop", "")
                    if c:
                        crop_counts[c] = crop_counts.get(c, 0) + 1
                        total_active += 1
                elif tile.get("kind") in ("COOP", "PASTURE"):
                    a = tile.get("animal", "")
                    if a:
                        crop_counts[a] = crop_counts.get(a, 0) + 1
                        total_active += 1

        results = []

        for crop in self.ONE_TIME_CROPS:
            candidate = self.evaluate(crop, state)
            if candidate.season_feasible:
                results.append(candidate)

        for animal in self.ANIMAL_PROFILES:
            candidate = self.evaluate_animal(animal, state)
            if candidate is not None and candidate.season_feasible:
                if state.me.money >= self.ANIMAL_PROFILES[animal]["cost"]:
                    results.append(candidate)

        def _diversity_score(item: SlotCandidate) -> float:
            base = item.contribution_per_tile_day

            # Add pseudo-random optimism for exploration
            cycle = int(state.step) // 5
            pseudo_hash = hash(f"{item.crop}_{cycle}")
            optimism = 0.85 + (abs(pseudo_hash) % 31) / 100.0
            base_score = base * optimism

            if total_active == 0:
                return base_score

            cap = self.MELON_CAP if item.crop == "MELON" else self.DIVERSITY_CAP
            frac = crop_counts.get(item.crop, 0) / max(1, total_active)
            if frac >= cap:
                return base_score * 0.40
            return base_score

        results.sort(
            key=lambda item: (
                _diversity_score(item),
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

        Override: if day == 0 and we have enough money, force an animal
        to get the exponential growth started.
        """
        if self.free_slot_count(state) <= 0:
            return None

        current_day = int(state.day)

        # Forced early animal: if it's day 0 and we have at least 1300 cash,
        # choose GOOSE or COW (whichever ranks better) to kickstart production.
        if current_day == 0 and state.me.money >= 1300:
            goose = self.evaluate_animal("GOOSE", state)
            cow = self.evaluate_animal("COW", state)
            # Pick the one with higher contribution_per_tile_day
            candidates = [c for c in [goose, cow] if c is not None and c.season_feasible]
            if candidates:
                # Return the best one
                return max(candidates, key=lambda c: c.contribution_per_tile_day)

        ranked = self.rank(state)

        if not ranked:
            return None

        return ranked[0]

    def crop_portfolio(
        self,
        state,
        slots: int,
    ) -> list[str]:
        """
        Build a diversified crop batch for the currently free land.
        """
        slots = max(0, min(int(slots), self.free_slot_count(state)))
        if slots == 0:
            return []

        active_counts: dict[str, int] = {}
        active_total = 0
        for row in state.me.tiles:
            for tile in row:
                if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                    continue
                crop = str(tile.get("crop", ""))
                if crop in self.ONE_TIME_CROPS:
                    active_counts[crop] = active_counts.get(crop, 0) + 1
                    active_total += 1

        candidates = [
            self.evaluate(crop, state)
            for crop in self.ONE_TIME_CROPS
            if self.evaluate(crop, state).season_feasible
        ]
        allocation: list[str] = []

        for _ in range(slots):
            total_after = active_total + len(allocation) + 1

            def fraction(candidate: SlotCandidate) -> float:
                existing = active_counts.get(candidate.crop, 0)
                planned = allocation.count(candidate.crop)
                return (existing + planned + 1) / total_after

            eligible = [
                candidate for candidate in candidates
                if fraction(candidate) <= 0.50
            ]
            best = max(
                eligible or candidates,
                key=lambda candidate: candidate.contribution_per_tile_day,
                default=None,
            )
            if best is None:
                break
            allocation.append(best.crop)

        return allocation

    # ========================================================
    # DEBUG SUMMARY
    # ========================================================

    def explain(
        self,
        state,
    ) -> list[dict]:
        """Return a simple, serializable explanation of the ranking."""

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