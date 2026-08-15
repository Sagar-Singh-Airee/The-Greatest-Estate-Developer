"""
V2.0 Crop Economics Model.

This module contains the documented Kaggriculture crop
parameters and deterministic economic calculations.

Important:
    This module does NOT make farming decisions.

It only answers:

    "Given a crop, a sale price, and a production scenario,
     what is its expected economic contribution?"

V2.0 focuses on one-time crop economics first.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CropProfile:
    """
    Static crop mechanics from Kaggriculture.

    For one-time crops:
        first_yield_day
        max_yield_day
        max_yield
        base_price
    """

    name: str

    seed_cost: int

    first_yield_day: int

    max_yield_day: int

    max_yield_unfertilized: int

    max_yield_fertilized: int

    base_price: int

    yield_type: str

    # Ongoing crops add this many days between production ticks. One-time
    # crops use 0. This keeps planning logic tied to one authoritative cadence.
    yield_interval: int


# ============================================================
# DOCUMENTED CROP PROFILES
# ============================================================

CROP_PROFILES: dict[str, CropProfile] = {

    "WHEAT": CropProfile(
        name="WHEAT",
        seed_cost=10,
        first_yield_day=2,
        max_yield_day=4,
        # The engine's held-yield cap is 6, but the non-fertilized watering
        # window can bank four units; the sixth unit requires fertilizer.
        max_yield_unfertilized=4,
        max_yield_fertilized=6,
        base_price=25,
        yield_type="ONE_TIME",
        yield_interval=0,
    ),

    "CARROT": CropProfile(
        name="CARROT",
        seed_cost=20,
        first_yield_day=2,
        max_yield_day=3,
        max_yield_unfertilized=3,
        max_yield_fertilized=4,
        base_price=35,
        yield_type="ONE_TIME",
        yield_interval=0,
    ),

    "TOMATO": CropProfile(
        name="TOMATO",
        seed_cost=50,
        first_yield_day=8,
        # Four daily output ticks complete on day 11.
        max_yield_day=11,
        max_yield_unfertilized=4,
        max_yield_fertilized=4,
        base_price=60,
        yield_type="ONGOING",
        yield_interval=1,
    ),

    "STRAWBERRY": CropProfile(
        name="STRAWBERRY",
        seed_cost=100,
        first_yield_day=10,
        # Four two-day output ticks complete on day 16.
        max_yield_day=16,
        max_yield_unfertilized=4,
        max_yield_fertilized=4,
        base_price=120,
        yield_type="ONGOING",
        yield_interval=2,
    ),

    "MELON": CropProfile(
        name="MELON",
        seed_cost=80,
        first_yield_day=10,
        max_yield_day=12,
        max_yield_unfertilized=6,
        max_yield_fertilized=6,
        base_price=250,
        yield_type="ONE_TIME",
        yield_interval=0,
    ),
}


# ============================================================
# ECONOMIC RESULTS
# ============================================================


@dataclass(frozen=True)
class CropEconomics:
    """
    Calculated economics for one production scenario.
    """

    crop: str

    expected_yield: float

    price_per_unit: float

    gross_revenue: float

    seed_cost: float

    fertilizer_cost: float

    labor_cost: float

    movement_cost: float

    total_cost: float

    contribution: float

    contribution_per_day: float

    contribution_per_tile_day: float


# ============================================================
# BASIC CALCULATIONS
# ============================================================


def gross_revenue(
    expected_yield: float,
    price_per_unit: float,
) -> float:
    """Calculate gross revenue."""

    return (
        expected_yield
        * price_per_unit
    )


def total_cost(
    seed_cost: float,
    fertilizer_cost: float = 0.0,
    labor_cost: float = 0.0,
    movement_cost: float = 0.0,
) -> float:
    """Calculate total economic cost."""

    return (
        seed_cost
        + fertilizer_cost
        + labor_cost
        + movement_cost
    )


def contribution(
    expected_yield: float,
    price_per_unit: float,
    seed_cost: float,
    fertilizer_cost: float = 0.0,
    labor_cost: float = 0.0,
    movement_cost: float = 0.0,
) -> float:
    """Calculate net contribution before broader opportunity effects."""

    revenue = gross_revenue(
        expected_yield,
        price_per_unit,
    )

    costs = total_cost(
        seed_cost=seed_cost,
        fertilizer_cost=fertilizer_cost,
        labor_cost=labor_cost,
        movement_cost=movement_cost,
    )

    return revenue - costs


def contribution_per_day(
    contribution_value: float,
    production_days: int,
) -> float:
    """Normalize contribution by production duration."""

    if production_days <= 0:
        return 0.0

    return (
        contribution_value
        / production_days
    )


def contribution_per_tile_day(
    contribution_value: float,
    occupied_days: int,
) -> float:
    """
    Normalize contribution by tile occupancy.

    This is intentionally separate from contribution_per_day
    because future investment decisions care about scarce land.
    """

    if occupied_days <= 0:
        return 0.0

    return (
        contribution_value
        / occupied_days
    )


# ============================================================
# SCENARIO BUILDER
# ============================================================


def evaluate_crop(
    crop: str,
    *,
    price_per_unit: float | None = None,
    fertilized: bool = False,
    fertilizer_cost: float = 0.0,
    labor_cost: float = 0.0,
    movement_cost: float = 0.0,
) -> CropEconomics:
    """
    Evaluate a crop under a simple deterministic scenario.

    V2.0 assumes:
        - optimal watering
        - harvest/production at the documented economic window
        - no market impact from our own sale
        - supplied price_per_unit is the realized price
    """

    if crop not in CROP_PROFILES:
        raise ValueError(
            f"Unknown crop: {crop}"
        )

    profile = CROP_PROFILES[crop]

    if price_per_unit is None:
        price_per_unit = profile.base_price

    if profile.yield_type == "ONE_TIME":

        if fertilized:
            expected_yield = (
                profile.max_yield_fertilized
            )

        else:
            expected_yield = (
                profile.max_yield_unfertilized
            )

        occupied_days = (
            profile.max_yield_day
        )

    else:

        # Ongoing crops produce multiple scheduled yields.
        # V2.0 deliberately uses their documented maximum
        # cumulative production of 4 for a closed comparison.
        expected_yield = (
            profile.max_yield_unfertilized
        )

        occupied_days = (
            profile.max_yield_day
        )

    net = contribution(
        expected_yield=expected_yield,
        price_per_unit=price_per_unit,
        seed_cost=profile.seed_cost,
        fertilizer_cost=fertilizer_cost,
        labor_cost=labor_cost,
        movement_cost=movement_cost,
    )

    return CropEconomics(
        crop=crop,
        expected_yield=float(
            expected_yield
        ),
        price_per_unit=float(
            price_per_unit
        ),
        gross_revenue=float(
            gross_revenue(
                expected_yield,
                price_per_unit,
            )
        ),
        seed_cost=float(
            profile.seed_cost
        ),
        fertilizer_cost=float(
            fertilizer_cost
        ),
        labor_cost=float(
            labor_cost
        ),
        movement_cost=float(
            movement_cost
        ),
        total_cost=float(
            total_cost(
                profile.seed_cost,
                fertilizer_cost,
                labor_cost,
                movement_cost,
            )
        ),
        contribution=float(net),
        contribution_per_day=float(
            contribution_per_day(
                net,
                profile.max_yield_day,
            )
        ),
        contribution_per_tile_day=float(
            contribution_per_tile_day(
                net,
                occupied_days,
            )
        ),
    )


def rank_crops(
    *,
    price_overrides: dict[str, float] | None = None,
) -> list[CropEconomics]:
    """
    Rank crops by contribution per tile-day.

    This is an analytical ranking only.
    """

    price_overrides = (
        price_overrides or {}
    )

    results = []

    for crop in CROP_PROFILES:

        result = evaluate_crop(
            crop,
            price_per_unit=price_overrides.get(
                crop
            ),
        )

        results.append(result)

    results.sort(
        key=lambda item: (
            item.contribution_per_tile_day
        ),
        reverse=True,
    )

    return results