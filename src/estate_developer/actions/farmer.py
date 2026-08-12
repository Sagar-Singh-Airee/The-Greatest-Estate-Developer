
"""
V1.1 Controlled Two-Cell Wheat Scheduler.

The farmer manages exactly two production cells:

    A = (3, 4)
    B = (2, 4)

The goal is to increase utilization of the main farmer
without exceeding a workload that one farmer can reliably
service.

Priority:
    1. Critical water
    2. Harvest ready crop
    3. Normal water
    4. Move harvested wheat to shed
    5. Plant available seed
    6. PASS

No:
    - market optimization
    - fertilizer
    - animals
    - land expansion
    - weed chasing
"""

from __future__ import annotations

from estate_developer.state.parser import ObservationState


class ReliableFarmer:
    """Two-cell wheat task scheduler."""

    CROP = "WHEAT"

    PRODUCTION_TILES = (
        (3, 4),
        (2, 4),
    )

    SHED_TILE = (4, 4)

    def decide(
        self,
        state: ObservationState,
    ) -> list[str]:

        farm = state.me
        x = farm.farmer.x
        y = farm.farmer.y

        # ----------------------------------------------------
        # 1. HARVEST READY CROPS
        # ----------------------------------------------------

        harvest_target = self._best_harvest_target(
            farm.tiles
        )

        if harvest_target is not None:

            tx, ty = harvest_target

            if (x, y) != (tx, ty):
                return self._move_toward(
                    x,
                    y,
                    tx,
                    ty,
                )

            return ["HARVEST"]

        # ----------------------------------------------------
        # 2. CRITICAL WATER
        #
        # Any unwatered active wheat receives priority.
        # ----------------------------------------------------

        critical_water = self._best_water_target(
            farm.tiles,
            critical_only=True,
        )

        if critical_water is not None:

            tx, ty = critical_water

            if (x, y) != (tx, ty):
                return self._move_toward(
                    x,
                    y,
                    tx,
                    ty,
                )

            return ["WATER"]

        # ----------------------------------------------------
        # 3. NORMAL WATER
        # ----------------------------------------------------

        normal_water = self._best_water_target(
            farm.tiles,
            critical_only=False,
        )

        if normal_water is not None:

            tx, ty = normal_water

            if (x, y) != (tx, ty):
                return self._move_toward(
                    x,
                    y,
                    tx,
                    ty,
                )

            return ["WATER"]

        # ----------------------------------------------------
        # 4. HARVESTED WHEAT → SHED
        # ----------------------------------------------------

        carried = self._carried_wheat(state)

        if carried > 0:

            if (x, y) != self.SHED_TILE:
                return self._move_toward(
                    x,
                    y,
                    self.SHED_TILE[0],
                    self.SHED_TILE[1],
                )

            return [
                "PLACE",
                self.CROP,
                carried,
            ]

        # ----------------------------------------------------
        # 5. PLANT A SEED ON AN AVAILABLE PRODUCTION CELL
        # ----------------------------------------------------

        seeds = int(
            state.private.seeds.get(
                self.CROP,
                0,
            )
        )

        if seeds > 0:

            plant_target = self._best_plant_target(
                farm.tiles
            )

            if plant_target is not None:

                tx, ty = plant_target

                if (x, y) != (tx, ty):
                    return self._move_toward(
                        x,
                        y,
                        tx,
                        ty,
                    )

                return [
                    "PLANT",
                    self.CROP,
                ]

        # ----------------------------------------------------
        # 6. NOTHING URGENT
        # ----------------------------------------------------

        return ["PASS"]

    # ========================================================
    # TASK SELECTION
    # ========================================================

    @classmethod
    def _best_harvest_target(
        cls,
        tiles,
    ):
        """
        Pick the ready production tile with the greatest yield.
        """

        candidates = []

        for position in cls.PRODUCTION_TILES:

            tile = cls._tile_at(
                tiles,
                *position,
            )

            if not cls._is_wheat(tile):
                continue

            yield_units = int(
                tile.get(
                    "yield_units",
                    0,
                )
            )

            if yield_units <= 0:
                continue

            # V1.1 harvests once wheat reaches the proven
            # unfertilized peak yield.
            if yield_units >= 4:
                candidates.append(
                    (
                        -yield_units,
                        position,
                    )
                )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item[0]
        )

        return candidates[0][1]

    @classmethod
    def _best_water_target(
        cls,
        tiles,
        *,
        critical_only: bool,
    ):
        """
        Find a wheat cell that has not been watered today.

        For critical_only=True we prioritize crops with the
        highest consecutive_unwatered value.
        """

        candidates = []

        for position in cls.PRODUCTION_TILES:

            tile = cls._tile_at(
                tiles,
                *position,
            )

            if not cls._is_wheat(tile):
                continue

            if tile.get(
                "watered_today",
                False,
            ):
                continue

            unwatered = int(
                tile.get(
                    "consecutive_unwatered",
                    0,
                )
            )

            if critical_only and unwatered < 1:
                continue

            # Higher risk first.
            candidates.append(
                (
                    -unwatered,
                    position,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1][1],
                item[1][0],
            )
        )

        return candidates[0][1]

    @classmethod
    def _best_plant_target(
        cls,
        tiles,
    ):
        """Return the first empty controlled production cell."""

        for position in cls.PRODUCTION_TILES:

            tile = cls._tile_at(
                tiles,
                *position,
            )

            if tile is None:
                return position

        return None

    # ========================================================
    # STATE HELPERS
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

    @staticmethod
    def _is_wheat(tile) -> bool:
        return (
            isinstance(tile, dict)
            and tile.get("kind") == "PLANT"
            and tile.get("crop") == "WHEAT"
        )

    @staticmethod
    def _carried_wheat(
        state: ObservationState,
    ) -> int:

        if not state.private.inventories:
            return 0

        return int(
            state.private.inventories[0].get(
                "WHEAT",
                0,
            )
        )

    # ========================================================
    # MOVEMENT
    # ========================================================

    @staticmethod
    def _move_toward(
        x: int,
        y: int,
        tx: int,
        ty: int,
    ) -> list[str]:

        if x < tx:
            return ["EAST"]

        if x > tx:
            return ["WEST"]

        if y < ty:
            return ["SOUTH"]

        if y > ty:
            return ["NORTH"]

        return ["PASS"]
