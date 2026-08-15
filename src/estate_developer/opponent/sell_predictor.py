"""
V13 Opponent Sell Predictor.

Estimates when the opponent will harvest and sell their crops/animals.
"""

from __future__ import annotations

from collections import defaultdict

from estate_developer.simulation.reference_rules import (
    ANIMALS,
    CROPS,
    TURNS_PER_DAY,
)
from estate_developer.state.parser import ObservationState, FarmState


class OpponentSellPredictor:
    """Predict opponent's future sell timings and volumes."""

    def __init__(self, state: ObservationState):
        self.state = state
        self.opponent: FarmState = state.opponent
        self.current_day = state.day

    def predict_sell_events(self) -> dict[str, list[tuple[int, int]]]:
        """
        Returns dict product -> list of (day, quantity) when opponent will sell.
        Assumes opponent sells immediately upon harvest maturity.
        """
        events = defaultdict(list)

        for y, row in enumerate(self.opponent.tiles):
            for x, tile in enumerate(row):
                if not isinstance(tile, dict):
                    continue

                kind = tile.get("kind")

                if kind == "PLANT":
                    crop = tile.get("crop")
                    if not crop:
                        continue
                    profile = CROPS.get(crop)
                    if not profile:
                        continue

                    planted_day = int(tile.get("planted_day", self.current_day))
                    age = self.current_day - planted_day
                    max_yield_day = int(profile["max_yield_day"])

                    # Estimate harvest day
                    if int(profile["ongoing"]):
                        # Ongoing: harvest every interval after first_yield_day
                        first = int(profile["first_yield_day"])
                        interval = int(profile["interval"])
                        # We estimate next harvest day
                        if age < first:
                            harvest_day = planted_day + first
                        else:
                            # Find next multiple after age
                            elapsed = age - first
                            next_interval = (elapsed // interval + 1) * interval
                            harvest_day = planted_day + first + next_interval
                        # Yield per harvest: 1 unit (in simulation)
                        quantity = 1
                    else:
                        # One-time: harvest at max_yield_day
                        harvest_day = planted_day + max_yield_day
                        # Yield: max_yield_unfertilized (approx)
                        quantity = int(profile.get("max_yield", 4))

                    if harvest_day > self.current_day:
                        product = crop
                        events[product].append((harvest_day, quantity))

                elif kind in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    if not animal:
                        continue
                    data = ANIMALS.get(animal)
                    if not data:
                        continue

                    placed_day = int(tile.get("placed_day", self.current_day))
                    age = self.current_day - placed_day
                    first = int(data["first_yield_day"])
                    interval = int(data["interval"])

                    # Animals produce every interval days after first.
                    if age < first:
                        harvest_day = placed_day + first
                    else:
                        elapsed = age - first
                        next_interval = (elapsed // interval + 1) * interval
                        harvest_day = placed_day + first + next_interval

                    product = str(data["product"])
                    # Each yield is 1 unit (max_held may allow more, but we assume 1)
                    quantity = 1
                    if harvest_day > self.current_day:
                        events[product].append((harvest_day, quantity))

        # Aggregate multiple events on same day
        aggregated = {}
        for product, event_list in events.items():
            # Sort by day and sum quantities per day
            day_sums = defaultdict(int)
            for day, qty in event_list:
                day_sums[day] += qty
            aggregated[product] = sorted(day_sums.items())

        return aggregated

    def opponent_sell_windows(
        self,
        horizon_days: int = 5,
    ) -> dict[str, list[int]]:
        """
        Returns dict product -> list of days (absolute) within horizon when opponent will sell.
        """
        events = self.predict_sell_events()
        windows = {}
        for product, day_qty_list in events.items():
            days = [day for day, _ in day_qty_list if day <= self.current_day + horizon_days]
            if days:
                windows[product] = days
        return windows