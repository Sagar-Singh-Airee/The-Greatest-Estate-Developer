
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

from estate_developer.simulation.reference_rules import (
    MARKET_I0,
    MARKET_PARAMS as REFERENCE_MARKET_PARAMS,
    market_price,
)


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
    item: MarketProfile(
        base_price=float(params["base"]),
        initial_inventory=MARKET_I0,
        throughput=float(params["T"]),
        below_function=str(params["below_func"]),
        below_target=float(params["below_target"]),
        above_function=str(params["above_func"]),
        above_target=float(params["above_target"]),
    )
    for item, params in REFERENCE_MARKET_PARAMS.items()
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

    # The former normalized-by-throughput approximation materially
    # overvalued premium crops. Quote the exact environment curve instead.
    return float(market_price(crop, int(inventory)))


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
