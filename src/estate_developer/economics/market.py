
"""
V2.1 Realized Market Economics.

Purpose:
    Estimate how a production quantity affects realized
    revenue under the documented market mechanics.

This is still an analysis layer.

It does NOT place trades.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MarketProfile:
    base_price: float
    initial_inventory: int
    throughput: float
    below_function: str
    below_target: float
    above_function: str
    above_target: float


MARKET_PROFILES = {

    "WHEAT": MarketProfile(
        base_price=25,
        initial_inventory=10000,
        throughput=400,
        below_function="sqrt",
        below_target=0.80,
        above_function="log",
        above_target=0.20,
    ),

    "CARROT": MarketProfile(
        base_price=35,
        initial_inventory=10000,
        throughput=450,
        below_function="log",
        below_target=0.20,
        above_function="sqrt",
        above_target=0.70,
    ),

    "TOMATO": MarketProfile(
        base_price=60,
        initial_inventory=10000,
        throughput=200,
        below_function="linear",
        below_target=0.40,
        above_function="sqrt",
        above_target=0.60,
    ),

    "STRAWBERRY": MarketProfile(
        base_price=120,
        initial_inventory=10000,
        throughput=100,
        below_function="sqrt",
        below_target=0.70,
        above_function="linear",
        above_target=1.60,
    ),

    "MELON": MarketProfile(
        base_price=250,
        initial_inventory=10000,
        throughput=300,
        below_function="log",
        below_target=0.20,
        above_function="sq",
        above_target=3.60,
    ),
}


@dataclass(frozen=True)
class SaleScenario:
    crop: str
    starting_inventory: int
    quantity: int
    starting_price: float
    ending_price: float
    realized_revenue: float
    average_price: float


def _shape(
    function: str,
    x: float,
) -> float:

    x = max(
        0.0,
        x,
    )

    if function == "linear":
        return x

    if function == "sq":
        return x * x

    if function == "sqrt":
        return math.sqrt(x)

    if function == "log":
        return math.log1p(x)

    if function == "log10":
        return math.log10(1.0 + x)

    raise ValueError(
        f"Unknown market shape: {function}"
    )


def _price_at_inventory(
    crop: str,
    inventory: float,
) -> float:

    profile = MARKET_PROFILES[crop]

    delta = inventory - profile.initial_inventory

    if abs(delta) < 1e-12:
        return profile.base_price

    if delta < 0:

        shape = _shape(
            profile.below_function,
            abs(delta) / profile.throughput,
        )

        amplitude = (
            profile.below_target
            * profile.base_price
            / _shape(
                profile.below_function,
                1.0,
            )
        )

        price = (
            profile.base_price
            + amplitude * shape
        )

    else:

        shape = _shape(
            profile.above_function,
            delta / profile.throughput,
        )

        amplitude = (
            profile.above_target
            * profile.base_price
            / _shape(
                profile.above_function,
                1.0,
            )
        )

        price = (
            profile.base_price
            - amplitude * shape
        )

    return max(
        1.0,
        round(price),
    )


def simulate_sale(
    crop: str,
    *,
    starting_inventory: int | None = None,
    quantity: int,
) -> SaleScenario:

    if crop not in MARKET_PROFILES:
        raise ValueError(
            f"Unknown crop: {crop}"
        )

    if quantity < 0:
        raise ValueError(
            "quantity must be >= 0"
        )

    profile = MARKET_PROFILES[crop]

    inventory = (
        profile.initial_inventory
        if starting_inventory is None
        else starting_inventory
    )

    starting_price = _price_at_inventory(
        crop,
        inventory,
    )

    revenue = 0.0

    # Market sales are processed one unit at a time.
    for _ in range(quantity):

        price = _price_at_inventory(
            crop,
            inventory,
        )

        revenue += price

        # Sale adds one unit to market inventory.
        inventory += 1

    ending_price = _price_at_inventory(
        crop,
        inventory,
    )

    average_price = (
        revenue / quantity
        if quantity > 0
        else 0.0
    )

    return SaleScenario(
        crop=crop,
        starting_inventory=inventory - quantity,
        quantity=quantity,
        starting_price=starting_price,
        ending_price=ending_price,
        realized_revenue=revenue,
        average_price=average_price,
    )
