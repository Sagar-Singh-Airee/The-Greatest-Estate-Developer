
"""
V2.15 Cycle-Level Economic Accounting.

Groups low-level FarmEvents into production cycles.

A cycle is approximately:

    BUY_SEED
        ↓
    PLANT
        ↓
    WATER*
        ↓
    HARVEST
        ↓
    PLACE
        ↓
    SELL

The implementation uses actual observed event order and
positions rather than theoretical crop duration.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict


@dataclass
class ProductionCycle:

    cycle_id: int

    crop: str

    position: tuple[int, int] | None

    seed_purchase_step: int | None = None

    plant_step: int | None = None

    harvest_step: int | None = None

    first_place_step: int | None = None

    sell_step: int | None = None

    seed_cost: float = 0.0

    quantity_sold: int = 0

    gross_revenue: float = 0.0

    water_events: int = 0

    place_events: int = 0

    duration_days: float = 0.0

    contribution: float = 0.0

    contribution_per_water: float = 0.0

    contribution_per_day: float = 0.0

    status: str = "OPEN"


class CycleTracker:
    """
    Reconstruct production cycles from FarmEvents.

    Position is important because a farm may have multiple
    simultaneous production slots.
    """

    def __init__(self) -> None:

        self.open_cycles = {}

        self.completed_cycles = []

        self.next_cycle_id = 1

    # ========================================================
    # PUBLIC
    # ========================================================

    def process(
        self,
        events,
    ) -> list[ProductionCycle]:

        # Process strictly in game-time order.
        ordered = sorted(
            events,
            key=lambda event: (
                event.step,
                event.hour,
            ),
        )

        for event in ordered:

            event_type = (
                event.event_type.value
            )

            crop = event.crop

            if crop is None:
                continue

            # ------------------------------------------------
            # BUY_SEED
            #
            # Seed purchase is associated with the next planting
            # of the same crop.
            # ------------------------------------------------

            if event_type == "BUY_SEED":

                key = (
                    crop,
                    "UNPLANTED",
                )

                state = self.open_cycles.setdefault(
                    key,
                    {
                        "seed_event": event,
                        "cycle": None,
                    },
                )

                # Keep the earliest outstanding seed.
                if state["seed_event"] is None:
                    state["seed_event"] = event

            # ------------------------------------------------
            # PLANT
            # ------------------------------------------------

            elif event_type == "PLANT":

                position = event.position

                cycle = ProductionCycle(
                    cycle_id=self.next_cycle_id,
                    crop=crop,
                    position=position,
                    seed_purchase_step=None,
                    plant_step=event.step,
                )

                self.next_cycle_id += 1

                # Attach the oldest outstanding seed purchase
                # of this crop when available.
                seed_key = (
                    crop,
                    "UNPLANTED",
                )

                pending_seed = (
                    self.open_cycles.pop(
                        seed_key,
                        None,
                    )
                )

                if pending_seed is not None:

                    seed_event = (
                        pending_seed["seed_event"]
                    )

                    if seed_event is not None:

                        cycle.seed_purchase_step = (
                            seed_event.step
                        )

                        cycle.seed_cost = (
                            self._seed_cost_from_event(
                                seed_event
                            )
                        )

                self.open_cycles[
                    self._cycle_key(
                        crop,
                        position,
                    )
                ] = cycle

            # ------------------------------------------------
            # WATER
            # ------------------------------------------------

            elif event_type == "WATER":

                cycle = self._find_cycle(
                    crop,
                    event.position,
                )

                if cycle is not None:
                    cycle.water_events += 1

            # ------------------------------------------------
            # HARVEST
            # ------------------------------------------------

            elif event_type == "HARVEST":

                cycle = self._find_cycle(
                    crop,
                    event.position,
                )

                if cycle is not None:

                    cycle.harvest_step = (
                        event.step
                    )

            # ------------------------------------------------
            # PLACE
            # ------------------------------------------------

            elif event_type == "PLACE":

                cycle = self._find_recent_unplaced_cycle(
                    crop
                )

                if cycle is not None:

                    cycle.place_events += 1

                    if cycle.first_place_step is None:

                        cycle.first_place_step = (
                            event.step
                        )

            # ------------------------------------------------
            # SELL
            #
            # Sales don't contain position, so match to the
            # oldest completed-but-unsold cycle of this crop.
            # ------------------------------------------------

            elif event_type == "SELL":

                cycle = self._find_unsold_cycle(
                    crop
                )

                if cycle is not None:

                    cycle.sell_step = (
                        event.step
                    )

                    cycle.quantity_sold += (
                        event.quantity
                    )

                    cycle.gross_revenue += (
                        event.gross_revenue
                    )

                    self._complete_cycle(
                        cycle
                    )

        return list(
            self.completed_cycles
        )

    # ========================================================
    # COMPLETION
    # ========================================================

    def _complete_cycle(
        self,
        cycle: ProductionCycle,
    ) -> None:

        cycle.contribution = (
            cycle.gross_revenue
            - cycle.seed_cost
        )

        cycle.duration_days = (
            self._days_between(
                cycle.plant_step,
                cycle.sell_step,
            )
        )

        if cycle.water_events > 0:

            cycle.contribution_per_water = (
                cycle.contribution
                / cycle.water_events
            )

        if cycle.duration_days > 0:

            cycle.contribution_per_day = (
                cycle.contribution
                / cycle.duration_days
            )

        cycle.status = "COMPLETE"

        # Remove from open cycles.
        self.open_cycles.pop(
            self._cycle_key(
                cycle.crop,
                cycle.position,
            ),
            None,
        )

        self.completed_cycles.append(
            cycle
        )

    # ========================================================
    # FINDERS
    # ========================================================

    def _find_cycle(
        self,
        crop,
        position,
    ):

        if position is not None:

            return self.open_cycles.get(
                self._cycle_key(
                    crop,
                    position,
                )
            )

        # Fallback: find any open cycle.
        for cycle in self.open_cycles.values():

            if (
                isinstance(
                    cycle,
                    ProductionCycle,
                )
                and cycle.crop == crop
            ):
                return cycle

        return None

    def _find_recent_unplaced_cycle(
        self,
        crop,
    ):

        candidates = [
            cycle
            for cycle in self.open_cycles.values()
            if (
                isinstance(
                    cycle,
                    ProductionCycle,
                )
                and cycle.crop == crop
                and cycle.harvest_step is not None
                and cycle.first_place_step is None
            )
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda cycle: (
                cycle.harvest_step or -1
            ),
        )

    def _find_unsold_cycle(
        self,
        crop,
    ):

        candidates = [
            cycle
            for cycle in self.open_cycles.values()
            if (
                isinstance(
                    cycle,
                    ProductionCycle,
                )
                and cycle.crop == crop
                and cycle.harvest_step is not None
                and cycle.quantity_sold == 0
            )
        ]

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda cycle: (
                cycle.harvest_step or 10**9
            ),
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _cycle_key(
        crop,
        position,
    ):

        return (
            crop,
            position,
        )

    @staticmethod
    def _days_between(
        start_step,
        end_step,
    ):

        if (
            start_step is None
            or end_step is None
        ):
            return 0.0

        # Kaggriculture advances roughly 24 steps/day.
        # This is an observation-derived normalization.
        return (
            max(
                0,
                end_step - start_step,
            )
            / 24.0
        )

    @staticmethod
    def _seed_cost_from_event(
        event,
    ):

        from estate_developer.economics.crops import (
            CROP_PROFILES,
        )

        profile = CROP_PROFILES.get(
            event.crop
        )

        if profile is None:
            return 0.0

        return (
            profile.seed_cost
            * event.quantity
        )
