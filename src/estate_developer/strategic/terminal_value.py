from __future__ import annotations

from estate_developer.economics.crops import CROP_PROFILES
from estate_developer.simulation.reference_rules import (
    ANIMALS,
    EPISODE_STEPS,
    MARKET_PARAMS,
    TURNS_PER_DAY,
    market_price,
)
from estate_developer.state.parser import ObservationState


class TerminalValueCalculator:
    """Estimate final score margin using only valid game mechanics.

    The prior evaluator referenced fields that do not exist in ``CropProfile``.
    As soon as an ongoing crop entered a rollout, scoring raised an exception
    and the outer Kaggle wrapper fell back to ``PASS``. This version works
    directly from the V11 crop/animal timing model and values the same market
    price curve used by the simulator.
    """

    @staticmethod
    def _days_remaining(state: ObservationState) -> int:
        steps_left = max(0, EPISODE_STEPS - int(state.step))
        return (steps_left + TURNS_PER_DAY - 1) // TURNS_PER_DAY

    @staticmethod
    def _price(state: ObservationState, item: str) -> float:
        if item not in MARKET_PARAMS:
            return 0.0
        return float(
            state.market.prices.get(
                item,
                market_price(item, state.market.inventory.get(item, 10_000)),
            )
        )

    @classmethod
    def _liquid_value(
        cls,
        state: ObservationState,
        items: dict[str, int],
    ) -> float:
        """Value only items that can actually be sold through the market."""
        return sum(
            max(0, int(quantity)) * cls._price(state, item)
            for item, quantity in items.items()
            if item in MARKET_PARAMS and item != "FERTILIZER"
        )

    @classmethod
    def _plant_value(
        cls,
        state: ObservationState,
        tile: dict,
        days_remaining: int,
    ) -> float:
        crop = str(tile.get("crop", ""))
        profile = CROP_PROFILES.get(crop)
        if profile is None:
            return 0.0

        price = cls._price(state, crop)
        held = max(0, int(tile.get("yield_units", 0)))
        planted_day = int(tile.get("planted_day", state.day))
        age = max(0, int(state.day) - planted_day)

        if profile.yield_type == "ONE_TIME":
            if held > 0:
                return held * price
            days_to_first = max(0, profile.first_yield_day - age)
            if days_remaining < days_to_first:
                return 0.0
            return profile.max_yield_unfertilized * price * 0.75

        # Ongoing crops have a fixed number of production ticks (their held
        # yield cap) in the reference engine. Estimate only reachable ticks.
        days_to_first = max(0, profile.first_yield_day - age)
        if days_remaining < days_to_first:
            future_ticks = 0
        else:
            future_ticks = 1 + (
                (days_remaining - days_to_first) // profile.yield_interval
            )
        remaining_capacity = max(0, profile.max_yield_unfertilized - held)
        future_units = min(remaining_capacity, future_ticks)
        return (held + future_units * 0.75) * price

    @classmethod
    def _animal_value(
        cls,
        state: ObservationState,
        tile: dict,
        days_remaining: int,
        *,
        ours: bool,
    ) -> float:
        animal = str(tile.get("animal", ""))
        data = ANIMALS.get(animal)
        if data is None:
            return 0.0

        product = str(data["product"])
        price = cls._price(state, product)
        held = max(0, int(tile.get("yield_units", 0)))
        placed_day = int(tile.get("placed_day", state.day))
        age = max(0, int(state.day) - placed_day)
        days_to_first = max(0, int(data["first_yield_day"]) - age)
        interval = max(1, int(data["interval"]))
        future_yields = (
            0
            if days_remaining < days_to_first
            else 1 + (days_remaining - days_to_first) // interval
        )

        # Animals require feeding, care, collection, and sale. Discount future
        # output instead of treating them as a cost-free perpetual machine.
        execution_factor = 0.62 if ours else 0.55
        return (held + future_yields * execution_factor) * price

    @classmethod
    def _farm_future_value(
        cls,
        state: ObservationState,
        tiles: list[list[object]],
        days_remaining: int,
        *,
        ours: bool,
    ) -> float:
        value = 0.0
        for row in tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if tile.get("kind") == "PLANT":
                    value += cls._plant_value(state, tile, days_remaining)
                elif tile.get("kind") in ("COOP", "PASTURE"):
                    value += cls._animal_value(
                        state, tile, days_remaining, ours=ours
                    )
        return value

    @classmethod
    def calculate(cls, state: ObservationState) -> float:
        """Return estimated final cash margin: our score minus theirs."""
        days_remaining = cls._days_remaining(state)

        ours = float(state.me.money)
        ours += cls._liquid_value(state, state.private.shed)
        for inventory in state.private.inventories:
            ours += cls._liquid_value(state, inventory)
        ours += cls._farm_future_value(
            state, state.me.tiles, days_remaining, ours=True
        )

        opponent = float(state.opponent.money)
        opponent += cls._farm_future_value(
            state, state.opponent.tiles, days_remaining, ours=False
        )

        return ours - opponent
