
"""
V2.14 Empirical Cycle Economics.

Uses observed telemetry rather than theoretical workload
assumptions.

Goal:
    Measure what the CURRENT AGENT actually spends and earns.
"""

from __future__ import annotations

from dataclasses import dataclass

from estate_developer.economics.crops import (
    CROP_PROFILES,
)


@dataclass(frozen=True)
class EmpiricalCropMetrics:

    crop: str

    seeds: int
    plants: int
    waters: int
    harvests: int
    placed: int
    sold: int

    seed_cost: float
    total_seed_spend: float

    average_yield_per_harvest: float

    waters_per_harvest: float
    farmer_actions_per_harvest: float

    observed_revenue: float
    observed_contribution: float

    contribution_per_harvest: float
    contribution_per_water: float
    contribution_per_farmer_action: float


def analyze_crop(
    crop: str,
    stats: dict,
    *,
    observed_revenue: float,
) -> EmpiricalCropMetrics:

    if crop not in CROP_PROFILES:
        raise ValueError(
            f"Unknown crop: {crop}"
        )

    profile = CROP_PROFILES[crop]

    seeds = int(
        stats.get(
            "seed_purchases",
            0,
        )
    )

    plants = int(
        stats.get(
            "plants",
            0,
        )
    )

    waters = int(
        stats.get(
            "waters",
            0,
        )
    )

    harvests = int(
        stats.get(
            "harvests",
            0,
        )
    )

    placed = int(
        stats.get(
            "placed",
            0,
        )
    )

    sold = int(
        stats.get(
            "units_sold",
            0,
        )
    )

    seed_spend = (
        seeds
        * profile.seed_cost
    )

    average_yield = (
        sold / harvests
        if harvests > 0
        else 0.0
    )

    waters_per_harvest = (
        waters / harvests
        if harvests > 0
        else 0.0
    )

    # Core farmer operations measured directly.
    #
    # PLANT + WATER + HARVEST + PLACE.
    farmer_actions = (
        plants
        + waters
        + harvests
        + placed * 0
    )

    # We deliberately do not count PLACE as a separate
    # farmer-action cost here because `placed` is quantity,
    # not event count in the current ledger.
    farmer_actions_per_harvest = (
        farmer_actions / harvests
        if harvests > 0
        else 0.0
    )

    contribution = (
        observed_revenue
        - seed_spend
    )

    contribution_per_harvest = (
        contribution / harvests
        if harvests > 0
        else 0.0
    )

    contribution_per_water = (
        contribution / waters
        if waters > 0
        else 0.0
    )

    contribution_per_farmer_action = (
        contribution
        / farmer_actions
        if farmer_actions > 0
        else 0.0
    )

    return EmpiricalCropMetrics(
        crop=crop,
        seeds=seeds,
        plants=plants,
        waters=waters,
        harvests=harvests,
        placed=placed,
        sold=sold,
        seed_cost=float(
            profile.seed_cost
        ),
        total_seed_spend=float(
            seed_spend
        ),
        average_yield_per_harvest=float(
            average_yield
        ),
        waters_per_harvest=float(
            waters_per_harvest
        ),
        farmer_actions_per_harvest=float(
            farmer_actions_per_harvest
        ),
        observed_revenue=float(
            observed_revenue
        ),
        observed_contribution=float(
            contribution
        ),
        contribution_per_harvest=float(
            contribution_per_harvest
        ),
        contribution_per_water=float(
            contribution_per_water
        ),
        contribution_per_farmer_action=float(
            contribution_per_farmer_action
        ),
    )
