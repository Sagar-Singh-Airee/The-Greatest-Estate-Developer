"""
Kaggriculture observation parser.

V0 responsibility:
    Convert the raw Kaggriculture observation into a stable, typed,
    strategy-friendly representation.

This module deliberately contains NO strategy.
It only answers:

    "What does the environment currently look like?"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Position:
    """Grid position."""

    x: int
    y: int


@dataclass(frozen=True)
class FarmState:
    """Public state of one farm."""

    money: float
    tiles: list[list[Any]]
    farmer: Position
    hands: list[Position]
    unlocked_quadrants: tuple[str, ...]
    hires_today: int


@dataclass(frozen=True)
class PrivateState:
    """Private state visible only to the current agent."""

    shed: dict[str, int]
    seeds: dict[str, int]
    inventories: list[dict[str, int]]


@dataclass(frozen=True)
class MarketState:
    """Shared market state."""

    inventory: dict[str, int]
    prices: dict[str, int]


@dataclass(frozen=True)
class TownState:
    """Shared town state."""

    unlocked_shops: tuple[str, ...]


@dataclass(frozen=True)
class ObservationState:
    """
    Parsed top-level Kaggriculture state.

    This is the object future systems will consume instead of reading
    raw obs dictionaries everywhere.
    """

    step: int
    day: int
    hour: int
    player: int
    remaining_overage_time: int

    farms: tuple[FarmState, FarmState]
    private: PrivateState
    market: MarketState
    town: TownState

    @property
    def me(self) -> FarmState:
        """Return our farm."""
        return self.farms[self.player]

    @property
    def opponent(self) -> FarmState:
        """Return the opponent's public farm."""
        return self.farms[1 - self.player]


class ObservationParser:
    """Convert raw Kaggriculture observations into ObservationState."""

    @staticmethod
    def _parse_position(value: Any) -> Position:
        """Parse [x, y] into Position."""
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError(f"Invalid position: {value!r}")

        return Position(
            x=int(value[0]),
            y=int(value[1]),
        )

    @classmethod
    def _parse_farm(cls, raw: dict[str, Any]) -> FarmState:
        """Parse one public farm."""
        required_keys = {
            "money",
            "tiles",
            "farmer",
            "hands",
            "unlocked_quadrants",
            "hires_today",
        }

        missing = required_keys - raw.keys()
        if missing:
            raise ValueError(
                f"Farm observation missing keys: {sorted(missing)}"
            )

        return FarmState(
            money=float(raw["money"]),
            tiles=raw["tiles"],
            farmer=cls._parse_position(raw["farmer"]),
            hands=tuple(
                cls._parse_position(position)
                for position in raw["hands"]
            ),
            unlocked_quadrants=tuple(raw["unlocked_quadrants"]),
            hires_today=int(raw["hires_today"]),
        )

    @staticmethod
    def _parse_private(raw: dict[str, Any]) -> PrivateState:
        """Parse private player state."""
        required_keys = {"shed", "seeds", "inventories"}

        missing = required_keys - raw.keys()
        if missing:
            raise ValueError(
                f"Private observation missing keys: {sorted(missing)}"
            )

        return PrivateState(
            shed=dict(raw["shed"]),
            seeds=dict(raw["seeds"]),
            inventories=[
                dict(inventory)
                for inventory in raw["inventories"]
            ],
        )

    @staticmethod
    def _parse_market(raw: dict[str, Any]) -> MarketState:
        """Parse market state."""
        required_keys = {"inventory", "prices"}

        missing = required_keys - raw.keys()
        if missing:
            raise ValueError(
                f"Market observation missing keys: {sorted(missing)}"
            )

        return MarketState(
            inventory=dict(raw["inventory"]),
            prices=dict(raw["prices"]),
        )

    @staticmethod
    def _parse_town(raw: dict[str, Any]) -> TownState:
        """Parse town state."""
        if "unlocked_shops" not in raw:
            raise ValueError(
                "Town observation missing 'unlocked_shops'"
            )

        return TownState(
            unlocked_shops=tuple(raw["unlocked_shops"]),
        )

    @classmethod
    def parse(cls, obs: dict[str, Any]) -> ObservationState:
        """
        Parse one raw Kaggriculture observation.

        Raises:
            ValueError: if the observation structure is invalid.
        """
        required_keys = {
            "remainingOverageTime",
            "step",
            "player",
            "farms",
            "private",
            "market",
            "town",
            "day",
            "hour",
        }

        missing = required_keys - obs.keys()
        if missing:
            raise ValueError(
                f"Observation missing keys: {sorted(missing)}"
            )

        farms = obs["farms"]

        if not isinstance(farms, list) or len(farms) != 2:
            raise ValueError(
                f"Expected exactly two farms, got: {type(farms)!r}"
            )

        player = int(obs["player"])

        if player not in (0, 1):
            raise ValueError(
                f"Invalid player index: {player}"
            )

        return ObservationState(
            step=int(obs["step"]),
            day=int(obs["day"]),
            hour=int(obs["hour"]),
            player=player,
            remaining_overage_time=int(
                obs["remainingOverageTime"]
            ),
            farms=(
                cls._parse_farm(farms[0]),
                cls._parse_farm(farms[1]),
            ),
            private=cls._parse_private(obs["private"]),
            market=cls._parse_market(obs["market"]),
            town=cls._parse_town(obs["town"]),
        )

