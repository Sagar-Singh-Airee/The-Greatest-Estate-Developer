
"""
V2.12 Dynamic Economic Task Generator.

Responsibilities:

    1. Discover work on the real farm.
    2. Protect existing crops.
    3. Detect free production slots.
    4. Ask the economic allocator which crop should occupy
       the next free slot.
    5. Generate BUY_SEED / PLANT tasks.

Important rule:

    Existing healthy crops are NEVER replaced.

Only empty production slots are economically allocated.
"""

from __future__ import annotations

from estate_developer.economics.slot_allocator import (
    ProductionSlotAllocator,
)

from estate_developer.planning.tasks import (
    FarmTask,
    TaskType,
)


class TaskGenerator:

    # --------------------------------------------------------
    # Fixed execution capacity discovered empirically.
    # --------------------------------------------------------

    MAX_PRODUCTION_SLOTS = 5

    PRODUCTION_TILES = (
        (3, 4),
        (2, 4),
        (3, 3),
        (2, 3),
        (1, 3),
    )

    # Economic candidates currently validated.
    CANDIDATE_CROPS = (
        "WHEAT",
        "CARROT",
        "MELON",
    )

    # Task priorities.
    HARVEST_PRIORITY = 1000
    WATER_CRITICAL_PRIORITY = 900
    WATER_NORMAL_PRIORITY = 800
    PLACE_PRIORITY = 700
    PLANT_PRIORITY = 600
    BUY_SEED_PRIORITY = 500

    def __init__(self) -> None:
        self.allocator = ProductionSlotAllocator()

    # ========================================================
    # MAIN GENERATION
    # ========================================================

    def generate(
        self,
        state,
        *,
        max_active_wheat: int = 3,
    ) -> list[FarmTask]:
        """
        Generate all currently actionable tasks.

        `max_active_wheat` is retained for compatibility with
        the V1.4 agent interface but is no longer used as a
        crop-specific limit.

        The actual constraint is:
            MAX_PRODUCTION_SLOTS = 5
        """

        tasks: list[FarmTask] = []

        active_slots = 0

        # ----------------------------------------------------
        # 1. Scan the controlled production area.
        # ----------------------------------------------------

        for x, y in self.PRODUCTION_TILES:

            tile = self._tile_at(
                state.me.tiles,
                x,
                y,
            )

            if tile == "LOCKED":
                continue

            # Empty slot.
            if tile is None:
                continue

            # Only actual plant objects count as occupied
            # production slots.
            if not isinstance(tile, dict):
                continue

            if tile.get("kind") != "PLANT":
                continue

            crop = tile.get("crop")

            if crop not in self.CANDIDATE_CROPS:
                continue

            active_slots += 1

            # ------------------------------------------------
            # HARVEST
            # ------------------------------------------------

            if self._is_harvest_ready(
                tile,
                crop,
            ):

                tasks.append(
                    FarmTask(
                        task_type=TaskType.HARVEST,
                        priority=self.HARVEST_PRIORITY,
                        target=(x, y),
                        crop=crop,
                        reason=(
                            f"{crop.lower()} reached "
                            "peak batch yield"
                        ),
                    )
                )

                # Harvest is more important than routine water.
                continue

            # ------------------------------------------------
            # WATER
            # ------------------------------------------------

            if not tile.get(
                "watered_today",
                False,
            ):

                unwatered = int(
                    tile.get(
                        "consecutive_unwatered",
                        0,
                    )
                )

                if unwatered >= 1:

                    priority = (
                        self.WATER_CRITICAL_PRIORITY
                    )

                    reason = (
                        f"{crop.lower()} is approaching "
                        "watering failure"
                    )

                else:

                    priority = (
                        self.WATER_NORMAL_PRIORITY
                    )

                    reason = (
                        f"{crop.lower()} requires "
                        "daily watering"
                    )

                tasks.append(
                    FarmTask(
                        task_type=TaskType.WATER,
                        priority=priority,
                        target=(x, y),
                        crop=crop,
                        reason=reason,
                    )
                )

        # ----------------------------------------------------
        # 2. Harvested inventory → shed.
        # ----------------------------------------------------

        inventory = (
            state.private.inventories[0]
            if state.private.inventories
            else {}
        )

        for crop in self.CANDIDATE_CROPS:

            quantity = int(
                inventory.get(
                    crop,
                    0,
                )
            )

            if quantity > 0:

                tasks.append(
                    FarmTask(
                        task_type=TaskType.PLACE,
                        priority=self.PLACE_PRIORITY,
                        crop=crop,
                        quantity=quantity,
                        reason=(
                            f"move harvested "
                            f"{crop.lower()} to shed"
                        ),
                    )
                )

                # One farmer inventory can normally contain
                # the current harvested batch. We still break
                # after adding the first discovered transfer.
                break

        # ----------------------------------------------------
        # 3. Economic allocation of a FREE slot.
        # ----------------------------------------------------

        if active_slots < self.MAX_PRODUCTION_SLOTS:

            candidate = self._best_feasible_crop(
                state
            )

            if candidate is not None:

                crop = candidate.crop

                seed_count = int(
                    state.private.seeds.get(
                        crop,
                        0,
                    )
                )

                # --------------------------------------------
                # Plant immediately if the correct seed exists.
                # --------------------------------------------

                if seed_count > 0:

                    target = (
                        self._find_empty_production_tile(
                            state.me.tiles
                        )
                    )

                    if target is not None:

                        tasks.append(
                            FarmTask(
                                task_type=TaskType.PLANT,
                                priority=self.PLANT_PRIORITY,
                                target=target,
                                crop=crop,
                                quantity=1,
                                reason=(
                                    "economic allocator selected "
                                    f"{crop}"
                                ),
                            )
                        )

                # --------------------------------------------
                # Otherwise buy exactly one seed.
                # --------------------------------------------

                else:

                    # Never buy if carrying goods or if a crop
                    # is still waiting in the shed.
                    if not self._farmer_carrying_any_candidate(
                        state
                    ) and not self._shed_contains_candidate(
                        state
                    ):

                        profile = self._profile(
                            crop
                        )

                        if (
                            state.me.money
                            >= profile.seed_cost
                        ):

                            tasks.append(
                                FarmTask(
                                    task_type=TaskType.BUY_SEED,
                                    priority=self.BUY_SEED_PRIORITY,
                                    crop=crop,
                                    quantity=1,
                                    reason=(
                                        "economic allocator "
                                        f"selected {crop}"
                                    ),
                                )
                            )

        # ----------------------------------------------------
        # 4. Fallback
        # ----------------------------------------------------

        if not tasks:

            tasks.append(
                FarmTask(
                    task_type=TaskType.PASS,
                    priority=0,
                    reason="no executable work",
                )
            )

        tasks.sort(
            key=lambda task: task.priority,
            reverse=True,
        )

        return tasks

    # ========================================================
    # ECONOMIC SELECTION
    # ========================================================

    def _best_feasible_crop(
        self,
        state,
    ):
        """Return best currently feasible economic crop."""

        ranked = self.allocator.rank(
            state
        )

        for candidate in ranked:

            if candidate.crop in self.CANDIDATE_CROPS:
                return candidate

        return None

    # ========================================================
    # CROP PROFILE
    # ========================================================

    @staticmethod
    def _profile(crop: str):
        from estate_developer.economics.crops import (
            CROP_PROFILES,
        )

        return CROP_PROFILES[crop]

    # ========================================================
    # HARVEST LOGIC
    # ========================================================

    @classmethod
    def _is_harvest_ready(
        cls,
        tile: dict,
        crop: str,
    ) -> bool:

        from estate_developer.economics.crops import (
            CROP_PROFILES,
        )

        profile = CROP_PROFILES[crop]

        yield_units = int(
            tile.get(
                "yield_units",
                0,
            )
        )

        # For current V2 candidates this represents peak
        # one-time batch yield.
        return (
            yield_units
            >= profile.max_yield_unfertilized
        )

    # ========================================================
    # INVENTORY
    # ========================================================

    def _farmer_carrying_any_candidate(
        self,
        state,
    ) -> bool:

        inventory = (
            state.private.inventories[0]
            if state.private.inventories
            else {}
        )

        return any(
            int(
                inventory.get(
                    crop,
                    0,
                )
            ) > 0
            for crop in self.CANDIDATE_CROPS
        )

    def _shed_contains_candidate(
        self,
        state,
    ) -> bool:

        return any(
            int(
                state.private.shed.get(
                    crop,
                    0,
                )
            ) > 0
            for crop in self.CANDIDATE_CROPS
        )

    # ========================================================
    # BOARD HELPERS
    # ========================================================

    @staticmethod
    def _tile_at(
        tiles,
        x: int,
        y: int,
    ):

        if y < 0 or y >= len(tiles):
            return None

        if x < 0 or x >= len(tiles[y]):
            return None

        return tiles[y][x]

    def _find_empty_production_tile(
        self,
        tiles,
    ):
        for x, y in self.PRODUCTION_TILES:

            tile = self._tile_at(
                tiles,
                x,
                y,
            )

            if tile is None:
                return (x, y)

        return None
