
"""
V2.2 Marginal Production Value.

Answers:

    "What is the economic value of producing one additional
     batch/unit of a crop from the current market state?"

This module does NOT make agent decisions.

It provides:
    - batch revenue
    - marginal revenue
    - marginal contribution
    - comparison between crops
"""

from __future__ import annotations

from dataclasses import dataclass

from estate_developer.economics.market import (
    simulate_sale,
)
from estate_developer.economics.crops import (
    CROP_PROFILES,
)


@dataclass(frozen=True)
class MarginalValue:

    crop: str

    current_quantity: int

    additional_quantity: int

    current_revenue: float

    expanded_revenue: float

    marginal_revenue: float

    additional_cost: float

    marginal_contribution: float

    marginal_contribution_per_unit: float


def marginal_batch_value(
    crop: str,
    *,
    current_quantity: int,
    additional_quantity: int,
    price_override: float | None = None,
    additional_cost: float = 0.0,
) -> MarginalValue:
    """
    Calculate the incremental value of producing additional
    quantity of a crop.

    current_quantity:
        Quantity that would already be sold into the market.

    additional_quantity:
        Additional production we are evaluating.

    price_override:
        Optional fixed realized price for controlled tests.

    additional_cost:
        Cost attributable to the additional production.

    Important:
        This measures marginal market revenue first.
        It does not yet include land or worker opportunity
        cost unless supplied explicitly.
    """

    if crop not in CROP_PROFILES:
        raise ValueError(
            f"Unknown crop: {crop}"
        )

    if current_quantity < 0:
        raise ValueError(
            "current_quantity must be >= 0"
        )

    if additional_quantity < 0:
        raise ValueError(
            "additional_quantity must be >= 0"
        )

    current = simulate_sale(
        crop,
        starting_inventory=None,
        quantity=current_quantity,
    )

    expanded = simulate_sale(
        crop,
        starting_inventory=None,
        quantity=(
            current_quantity
            + additional_quantity
        ),
    )

    current_revenue = (
        current.realized_revenue
    )

    expanded_revenue = (
        expanded.realized_revenue
    )

    marginal_revenue = (
        expanded_revenue
        - current_revenue
    )

    # By default, use seed cost only for the newly
    # evaluated batch when a complete crop batch is being
    # represented.
    #
    # The caller can override with a full opportunity cost.
    if additional_cost == 0:
        profile = CROP_PROFILES[crop]

        # Cost is intentionally per additional unit here.
        # Higher-level code can replace this with exact batch
        # costs when evaluating a full production tile.
        implied_unit_cost = (
            profile.seed_cost
            / max(
                1,
                additional_quantity,
            )
        )

        additional_cost = (
            implied_unit_cost
            * additional_quantity
        )

    marginal_contribution = (
        marginal_revenue
        - additional_cost
    )

    marginal_per_unit = (
        marginal_contribution
        / additional_quantity
        if additional_quantity > 0
        else 0.0
    )

    return MarginalValue(
        crop=crop,
        current_quantity=current_quantity,
        additional_quantity=additional_quantity,
        current_revenue=current_revenue,
        expanded_revenue=expanded_revenue,
        marginal_revenue=marginal_revenue,
        additional_cost=additional_cost,
        marginal_contribution=marginal_contribution,
        marginal_contribution_per_unit=marginal_per_unit,
    )


def batch_margin(
    crop: str,
    *,
    current_quantity: int,
    batch_quantity: int,
    batch_cost: float | None = None,
) -> MarginalValue:
    """
    Evaluate a complete production batch.

    This is more useful for crop decisions than individual
    units because a farmer produces crops in discrete batches.
    """

    if crop not in CROP_PROFILES:
        raise ValueError(
            f"Unknown crop: {crop}"
        )

    if batch_cost is None:
        batch_cost = (
            CROP_PROFILES[crop].seed_cost
        )

    return marginal_batch_value(
        crop,
        current_quantity=current_quantity,
        additional_quantity=batch_quantity,
        additional_cost=batch_cost,
    )


def rank_next_batch(
    quantities: dict[str, int],
    batch_sizes: dict[str, int],
) -> list[MarginalValue]:
    """
    Rank the next production batch for each crop.

    quantities:
        Current planned/sold quantity by crop.

    batch_sizes:
        Expected additional quantity from one production batch.
    """

    results = []

    for crop, batch_size in batch_sizes.items():

        current_quantity = quantities.get(
            crop,
            0,
        )

        result = batch_margin(
            crop,
            current_quantity=current_quantity,
            batch_quantity=batch_size,
        )

        results.append(result)

    results.sort(
        key=lambda item: (
            item.marginal_contribution_per_unit
        ),
        reverse=True,
    )

    return results
