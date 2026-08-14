from __future__ import annotations

import copy
from typing import Any

from estate_developer.state.parser import (
    ObservationState,
    FarmState,
    PrivateState,
    MarketState,
    TownState,
)


def deep_copy_tiles(tiles: list[list[Any]]) -> list[list[Any]]:
    """Fast deep copy for farm tiles."""
    return [
        [copy.deepcopy(tile) for tile in row]
        for row in tiles
    ]


def copy_farm_state(farm: FarmState) -> FarmState:
    return FarmState(
        money=farm.money,
        tiles=deep_copy_tiles(farm.tiles),
        farmer=farm.farmer,
        hands=farm.hands,
        unlocked_quadrants=farm.unlocked_quadrants,
        hires_today=farm.hires_today,
    )


def copy_private_state(private: PrivateState) -> PrivateState:
    return PrivateState(
        shed=private.shed.copy(),
        seeds=private.seeds.copy(),
        inventories=tuple(inv.copy() for inv in private.inventories),
    )


def copy_market_state(market: MarketState) -> MarketState:
    return MarketState(
        inventory=market.inventory.copy(),
        prices=market.prices.copy(),
    )


def copy_town_state(town: TownState) -> TownState:
    return TownState(
        unlocked_shops=town.unlocked_shops,
    )


def copy_observation(obs: ObservationState) -> ObservationState:
    """
    Creates a deep copy of the ObservationState suitable for simulation rollouts.
    """
    return ObservationState(
        step=obs.step,
        day=obs.day,
        hour=obs.hour,
        player=obs.player,
        remaining_overage_time=obs.remaining_overage_time,
        farms=tuple(copy_farm_state(f) for f in obs.farms), # type: ignore
        private=copy_private_state(obs.private),
        market=copy_market_state(obs.market),
        town=copy_town_state(obs.town),
    )
