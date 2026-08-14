
"""
V11 Simulation Context.

Carries deterministic information that is part of the real Kaggriculture
environment but is not present in the agent observation itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationContext:
    """
    Configuration needed to reproduce Kaggriculture transitions.

    `seed` is optional because ordinary observation-only planning does not
    know the hidden environment seed. Differential tests can provide the
    real seed explicitly.
    """

    seed: int | None = None

    board_size: int = 10
    turns_per_day: int = 24
    shed_capacity: int = 100

    weed_spawn_chance: float = 0.005

    town_shop_unlock_interval: int = 3
    town_shop_sell_interval: int = 2
    town_center_sell_interval: int = 6

    farm_hand_cost_mult: int = 10
    max_market_orders_per_turn: int = 10
