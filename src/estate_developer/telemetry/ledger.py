
"""
V2.14.1 Economic Ledger.

Aggregates:
    operational events
    transaction revenue
    seed spending
    net crop contribution
"""

from __future__ import annotations

from collections import defaultdict


class EconomicLedger:

    def summarize(
        self,
        events,
    ) -> dict:

        crops = defaultdict(
            lambda: {
                "seed_purchases": 0,
                "seed_spend": 0.0,

                "units_sold": 0,
                "sell_events": 0,

                "gross_revenue": 0.0,
                "average_realized_price": 0.0,

                "plants": 0,
                "waters": 0,
                "harvests": 0,
                "places": 0,
                "placed_units": 0,

                "contribution": 0.0,
            }
        )

        for event in events:

            crop = event.crop

            if crop is None:
                continue

            entry = crops[crop]

            event_type = (
                event.event_type.value
            )

            if event_type == "BUY_SEED":

                entry[
                    "seed_purchases"
                ] += event.quantity

                from estate_developer.economics.crops import (
                    CROP_PROFILES,
                )

                profile = CROP_PROFILES.get(
                    crop
                )

                if profile is not None:

                    spend = (
                        profile.seed_cost
                        * event.quantity
                    )

                    entry[
                        "seed_spend"
                    ] += spend

            elif event_type == "SELL":

                entry[
                    "units_sold"
                ] += event.quantity

                entry[
                    "sell_events"
                ] += 1

                entry[
                    "gross_revenue"
                ] += event.gross_revenue

            elif event_type == "PLANT":

                entry[
                    "plants"
                ] += 1

            elif event_type == "WATER":

                entry[
                    "waters"
                ] += 1

            elif event_type == "HARVEST":

                entry[
                    "harvests"
                ] += 1

            elif event_type == "PLACE":

                entry[
                    "places"
                ] += 1

                entry[
                    "placed_units"
                ] += event.quantity

        # ----------------------------------------------------
        # Derived metrics
        # ----------------------------------------------------

        result = {}

        for crop, entry in crops.items():

            units = entry["units_sold"]
            revenue = entry["gross_revenue"]
            seed_spend = entry["seed_spend"]

            entry[
                "average_realized_price"
            ] = (
                revenue / units
                if units > 0
                else 0.0
            )

            entry[
                "contribution"
            ] = (
                revenue
                - seed_spend
            )

            entry[
                "revenue_per_water"
            ] = (
                revenue / entry["waters"]
                if entry["waters"] > 0
                else 0.0
            )

            entry[
                "contribution_per_water"
            ] = (
                entry["contribution"]
                / entry["waters"]
                if entry["waters"] > 0
                else 0.0
            )

            entry[
                "contribution_per_plant"
            ] = (
                entry["contribution"]
                / entry["plants"]
                if entry["plants"] > 0
                else 0.0
            )

            result[crop] = dict(
                entry
            )

        return result
