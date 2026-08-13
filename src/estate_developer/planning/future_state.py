
"""
V3 mutable future-state model.

This module is isolated from V2.

The real parser uses frozen dataclasses. V3 needs mutable
planning objects so hypothetical actions can change:

    money
    tiles
    farmer position
    seeds
    inventories
    shed
    market state
    town state
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from estate_developer.state.parser import (
    ObservationState,
)


@dataclass
class FuturePosition:
    """Mutable planning position."""

    x: int
    y: int


@dataclass
class FutureFarm:
    """Mutable planning representation of one farm."""

    money: float
    tiles: list[list[Any]]
    farmer: FuturePosition
    hands: list[Any]
    unlocked_quadrants: list[str]
    hires_today: int


@dataclass
class FuturePrivate:
    """Mutable private planning state."""

    shed: dict[str, int]
    seeds: dict[str, int]
    inventories: list[dict[str, int]]


@dataclass
class FutureMarket:
    """Mutable market planning state."""

    inventory: dict[str, int]
    prices: dict[str, int]


@dataclass
class FutureTown:
    """Mutable town planning state."""

    unlocked_shops: list[str]


@dataclass
class FutureState:
    """Fully mutable hypothetical game state."""

    step: int
    day: int
    hour: int
    player: int
    remaining_overage_time: int

    farms: list[FutureFarm]

    private: FuturePrivate
    market: FutureMarket
    town: FutureTown

    @property
    def me(self) -> FutureFarm:
        """Return our planning farm."""

        return self.farms[
            self.player
        ]

    @property
    def opponent(self) -> FutureFarm:
        """Return the opponent planning farm."""

        return self.farms[
            1 - self.player
        ]


def _copy_farm(
    farm,
) -> FutureFarm:
    """
    Convert a frozen parser FarmState into a mutable FutureFarm.
    """

    return FutureFarm(
        money=float(
            farm.money
        ),
        tiles=deepcopy(
            farm.tiles
        ),
        farmer=FuturePosition(
            x=int(
                farm.farmer.x
            ),
            y=int(
                farm.farmer.y
            ),
        ),
        hands=deepcopy(
            list(
                farm.hands
            )
        ),
        unlocked_quadrants=list(
            farm.unlocked_quadrants
        ),
        hires_today=int(
            farm.hires_today
        ),
    )


def snapshot(
    state: ObservationState,
) -> FutureState:
    """
    Create a fully mutable planning snapshot.

    The original ObservationState is never modified.
    """

    return FutureState(
        step=int(
            state.step
        ),
        day=int(
            state.day
        ),
        hour=int(
            state.hour
        ),
        player=int(
            state.player
        ),
        remaining_overage_time=int(
            state.remaining_overage_time
        ),
        farms=[
            _copy_farm(
                state.farms[0]
            ),
            _copy_farm(
                state.farms[1]
            ),
        ],
        private=FuturePrivate(
            shed=deepcopy(
                state.private.shed
            ),
            seeds=deepcopy(
                state.private.seeds
            ),
            inventories=[
                deepcopy(
                    inventory
                )
                for inventory
                in state.private.inventories
            ],
        ),
        market=FutureMarket(
            inventory=deepcopy(
                state.market.inventory
            ),
            prices=deepcopy(
                state.market.prices
            ),
        ),
        town=FutureTown(
            unlocked_shops=list(
                state.town.unlocked_shops
            )
        ),
    )


def clone(
    state: FutureState,
) -> FutureState:
    """
    Deep-clone an existing FutureState.
    """

    return FutureState(
        step=int(
            state.step
        ),
        day=int(
            state.day
        ),
        hour=int(
            state.hour
        ),
        player=int(
            state.player
        ),
        remaining_overage_time=int(
            state.remaining_overage_time
        ),
        farms=deepcopy(
            state.farms
        ),
        private=deepcopy(
            state.private
        ),
        market=deepcopy(
            state.market
        ),
        town=deepcopy(
            state.town
        ),
    )
