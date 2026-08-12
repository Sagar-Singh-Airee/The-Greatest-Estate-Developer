
"""
Kaggriculture state-difference engine.

V0 responsibility:
    Compare two historical StateSnapshot objects and report
    what changed between them.

This module contains NO strategy.

It answers:

    "What changed since the previous observation?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .memory import StateSnapshot


@dataclass(frozen=True)
class FarmDiff:
    """Changes detected on one farm."""

    money_change: float

    farmer_position_changed: bool
    old_farmer_position: tuple[int, int]
    new_farmer_position: tuple[int, int]

    hand_count_change: int
    land_added: tuple[str, ...]
    land_removed: tuple[str, ...]

    crop_count_change: dict[str, int]
    animal_count_change: dict[str, int]


@dataclass(frozen=True)
class MarketDiff:
    """Changes detected in the market."""

    price_change: dict[str, int]
    inventory_change: dict[str, int]


@dataclass(frozen=True)
class StateDiff:
    """Complete difference between two observations."""

    step_from: int
    step_to: int

    day_from: int
    day_to: int

    hour_from: int
    hour_to: int

    our_farm: FarmDiff
    opponent_farm: FarmDiff
    market: MarketDiff

    shops_added: tuple[str, ...]
    shops_removed: tuple[str, ...]


class StateDiffEngine:
    """Compare two StateSnapshot objects."""

    @staticmethod
    def _dict_diff(
        previous: dict[str, int],
        current: dict[str, int],
    ) -> dict[str, int]:
        """Return current - previous for every observed key."""

        keys = set(previous) | set(current)

        result: dict[str, int] = {}

        for key in sorted(keys):
            change = current.get(key, 0) - previous.get(key, 0)

            if change != 0:
                result[key] = change

        return result

    @classmethod
    def _farm_diff(
        cls,
        previous,
        current,
    ) -> FarmDiff:
        """Compare two FarmSnapshot objects."""

        old_position = (
            previous.farmer_x,
            previous.farmer_y,
        )

        new_position = (
            current.farmer_x,
            current.farmer_y,
        )

        previous_land = set(previous.unlocked_quadrants)
        current_land = set(current.unlocked_quadrants)

        return FarmDiff(
            money_change=current.money - previous.money,

            farmer_position_changed=(
                old_position != new_position
            ),

            old_farmer_position=old_position,
            new_farmer_position=new_position,

            hand_count_change=(
                current.hand_count - previous.hand_count
            ),

            land_added=tuple(
                sorted(current_land - previous_land)
            ),

            land_removed=tuple(
                sorted(previous_land - current_land)
            ),

            crop_count_change=cls._dict_diff(
                previous.crop_counts,
                current.crop_counts,
            ),

            animal_count_change=cls._dict_diff(
                previous.animal_counts,
                current.animal_counts,
            ),
        )

    @classmethod
    def compare(
        cls,
        previous: StateSnapshot,
        current: StateSnapshot,
    ) -> StateDiff:
        """
        Compare two consecutive state snapshots.

        Raises:
            ValueError:
                If the snapshots are not in chronological order.
        """

        if current.step < previous.step:
            raise ValueError(
                "Current snapshot cannot be earlier than "
                "previous snapshot."
            )

        previous_shops = set(previous.unlocked_shops)
        current_shops = set(current.unlocked_shops)

        price_change = cls._dict_diff(
            previous.market.prices,
            current.market.prices,
        )

        inventory_change = cls._dict_diff(
            previous.market.inventory,
            current.market.inventory,
        )

        return StateDiff(
            step_from=previous.step,
            step_to=current.step,

            day_from=previous.day,
            day_to=current.day,

            hour_from=previous.hour,
            hour_to=current.hour,

            our_farm=cls._farm_diff(
                previous.our_farm,
                current.our_farm,
            ),

            opponent_farm=cls._farm_diff(
                previous.opponent_farm,
                current.opponent_farm,
            ),

            market=MarketDiff(
                price_change=price_change,
                inventory_change=inventory_change,
            ),

            shops_added=tuple(
                sorted(current_shops - previous_shops)
            ),

            shops_removed=tuple(
                sorted(previous_shops - current_shops)
            ),
        )
