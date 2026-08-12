
"""
V2.5 Farmer Capacity Economics.

Estimates the farmer-turn burden of a crop.

This is deliberately conservative and analytical.

It does NOT execute actions or change the agent.
"""

from __future__ import annotations

from dataclasses import dataclass

from estate_developer.economics.crops import (
    CROP_PROFILES,
)


@dataclass(frozen=True)
class LaborEstimate:
    crop: str
    production_days: int
    watering_actions: int
    harvest_actions: int
    planting_actions: int
    estimated_movement_actions: int
    total_farmer_actions: int
    actions_per_day: float


def estimate_labor(
    crop: str,
    *,
    movement_actions: int = 0,
) -> LaborEstimate:
    """
    Estimate main-farmer workload for one crop batch.

    Conservative assumptions:
        - plant = 1 action
        - one watering action per day while alive
        - one harvest action
        - movement supplied separately

    This is intentionally a first-order approximation.
    """

    if crop not in CROP_PROFILES:
        raise ValueError(
            f"Unknown crop: {crop}"
        )

    profile = CROP_PROFILES[crop]

    production_days = profile.max_yield_day

    # At minimum, one watering per day.
    watering_actions = production_days

    planting_actions = 1
    harvest_actions = 1

    total = (
        watering_actions
        + planting_actions
        + harvest_actions
        + movement_actions
    )

    return LaborEstimate(
        crop=crop,
        production_days=production_days,
        watering_actions=watering_actions,
        harvest_actions=harvest_actions,
        planting_actions=planting_actions,
        estimated_movement_actions=movement_actions,
        total_farmer_actions=total,
        actions_per_day=(
            total / production_days
            if production_days > 0
            else 0.0
        ),
    )
