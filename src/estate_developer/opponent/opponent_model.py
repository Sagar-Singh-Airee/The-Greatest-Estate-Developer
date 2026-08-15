from __future__ import annotations

from typing import Any
from collections import Counter
from estate_developer.state.parser import ObservationState, FarmState


class OpponentModel:
    """
    V9 Opponent Model.

    Tracks the opponent's farm state over time and infers
    their likely crop mix and sell pressure.
    """

    def __init__(self):
        self.history: list[FarmState] = []
        self.starting_cash: float = 0.0

    def update(self, state: ObservationState) -> None:
        """Updates the opponent model with the latest observation."""
        opponent = state.opponent
        if not self.history:
            self.starting_cash = opponent.money
        self.history.append(opponent)

    @property
    def current_cash(self) -> float:
        return self.history[-1].money if self.history else 0.0

    @property
    def cash_delta(self) -> float:
        """Change in cash from the start."""
        return self.current_cash - self.starting_cash

    @property
    def worker_count(self) -> int:
        return len(self.history[-1].hands) if self.history else 0

    @property
    def tile_count(self) -> int:
        if not self.history:
            return 0
        tiles = self.history[-1].tiles
        count = 0
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict) and tile.get("kind") != "EMPTY":
                    count += 1
        return count

    # ============================================================
    # V9 INTELLIGENCE
    # ============================================================

    def _scan_opponent_tiles(self) -> Counter:
        """Count crops and animals on the opponent's farm."""
        counts: Counter = Counter()
        if not self.history:
            return counts

        tiles = self.history[-1].tiles
        for row in tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                kind = tile.get("kind")
                if kind == "PLANT":
                    crop = tile.get("crop")
                    if crop:
                        counts[crop] += 1
                elif kind in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    if animal:
                        product = (
                            "EGG" if animal == "GOOSE"
                            else ("MILK" if animal == "COW" else "WOOL")
                        )
                        counts[product] += 1
        return counts

    def dominant_crop(self) -> str | None:
        """
        Returns the opponent's most-planted crop/product,
        or None if the opponent has nothing planted.
        """
        counts = self._scan_opponent_tiles()
        if not counts:
            return None
        return counts.most_common(1)[0][0]

    def estimated_sell_volume(self, resource: str) -> int:
        """
        Estimates how many units of `resource` the opponent is
        likely to sell soon, based on their planted tiles.

        For one-time crops: count of planted tiles × avg yield (3).
        For animal products: count of animals × 1 (conservative).
        """
        counts = self._scan_opponent_tiles()
        tile_count = counts.get(resource, 0)
        if tile_count == 0:
            return 0

        # One-time crops produce roughly 3-4 units per tile
        # Animals produce 1 unit per yield tick
        if resource in ("EGG", "MILK", "WOOL"):
            return tile_count  # 1 per animal per cycle
        return tile_count * 3  # avg one-time crop yield