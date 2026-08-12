
"""
Kaggriculture state memory.

V0 responsibility:
    Remember observations across turns.

This module does NOT make strategic decisions.
It only stores historical state that later systems can analyze.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from .parser import ObservationState


@dataclass(frozen=True)
class MarketSnapshot:
    """Small historical market snapshot."""

    step: int
    day: int
    hour: int
    prices: dict[str, int]
    inventory: dict[str, int]


@dataclass(frozen=True)
class FarmSnapshot:
    """Small historical snapshot of one farm."""

    step: int
    money: float
    farmer_x: int
    farmer_y: int
    hand_count: int
    unlocked_quadrants: tuple[str, ...]
    crop_counts: dict[str, int]
    animal_counts: dict[str, int]


@dataclass(frozen=True)
class StateSnapshot:
    """Historical snapshot of the environment."""

    step: int
    day: int
    hour: int
    player: int

    our_farm: FarmSnapshot
    opponent_farm: FarmSnapshot
    market: MarketSnapshot

    unlocked_shops: tuple[str, ...]


class StateMemory:
    """
    Store a bounded history of parsed observations.

    V0 intentionally keeps the implementation simple.
    Later versions can derive:
        - price velocity
        - production trends
        - opponent behavior
        - market pressure
    """

    def __init__(self, max_history: int = 720) -> None:
        if max_history < 1:
            raise ValueError("max_history must be >= 1")

        self.max_history = max_history
        self._history: deque[StateSnapshot] = deque(
            maxlen=max_history
        )

    @property
    def history(self) -> tuple[StateSnapshot, ...]:
        """Return all stored snapshots."""
        return tuple(self._history)

    @property
    def latest(self) -> Optional[StateSnapshot]:
        """Return the most recent snapshot."""
        if not self._history:
            return None

        return self._history[-1]

    def __len__(self) -> int:
        return len(self._history)

    @staticmethod
    def _count_tiles(
        farm: ObservationState,
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Count visible crops and animals on a farm."""
        crop_counts: dict[str, int] = {}
        animal_counts: dict[str, int] = {}

        for row in farm.tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue

                kind = tile.get("kind")

                if kind == "PLANT":
                    crop = tile.get("crop")
                    if crop:
                        crop_counts[crop] = (
                            crop_counts.get(crop, 0) + 1
                        )

                elif kind in {"COOP", "PASTURE"}:
                    animal = tile.get("animal")
                    if animal:
                        animal_counts[animal] = (
                            animal_counts.get(animal, 0) + 1
                        )

        return crop_counts, animal_counts

    @classmethod
    def _farm_snapshot(
        cls,
        farm,
        step: int,
    ) -> FarmSnapshot:
        """Convert a parsed farm into a compact snapshot."""
        crop_counts: dict[str, int] = {}
        animal_counts: dict[str, int] = {}

        for row in farm.tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue

                kind = tile.get("kind")

                if kind == "PLANT":
                    crop = tile.get("crop")
                    if crop:
                        crop_counts[crop] = (
                            crop_counts.get(crop, 0) + 1
                        )

                elif kind in {"COOP", "PASTURE"}:
                    animal = tile.get("animal")
                    if animal:
                        animal_counts[animal] = (
                            animal_counts.get(animal, 0) + 1
                        )

        return FarmSnapshot(
            step=step,
            money=farm.money,
            farmer_x=farm.farmer.x,
            farmer_y=farm.farmer.y,
            hand_count=len(farm.hands),
            unlocked_quadrants=farm.unlocked_quadrants,
            crop_counts=crop_counts,
            animal_counts=animal_counts,
        )

    def record(self, state: ObservationState) -> StateSnapshot:
        """
        Record one parsed observation.

        Returns the snapshot that was stored.
        """

        snapshot = StateSnapshot(
            step=state.step,
            day=state.day,
            hour=state.hour,
            player=state.player,
            our_farm=self._farm_snapshot(
                state.me,
                state.step,
            ),
            opponent_farm=self._farm_snapshot(
                state.opponent,
                state.step,
            ),
            market=MarketSnapshot(
                step=state.step,
                day=state.day,
                hour=state.hour,
                prices=dict(state.market.prices),
                inventory=dict(state.market.inventory),
            ),
            unlocked_shops=state.town.unlocked_shops,
        )

        self._history.append(snapshot)

        return snapshot

    def previous(self) -> Optional[StateSnapshot]:
        """Return the snapshot immediately before the latest one."""
        if len(self._history) < 2:
            return None

        return self._history[-2]

    def clear(self) -> None:
        """Clear all stored history."""
        self._history.clear()
