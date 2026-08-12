
"""
V1.2 Controlled Three-Cell Wheat Scheduler.

Production cells:
    A = (3, 4)
    B = (2, 4)
    C = (3, 3)

Hard production limit:
    3 active wheat plants.

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
    """Three-cell wheat task scheduler."""

    CROP = "WHEAT"

    PRODUCTION_TILES = (
        (3, 4),
        (2, 4),
        (3, 3),
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

        target = self._best_harvest_target(
            farm.tiles
        )

        if target is not None:
            tx, ty = target

            if (x, y) != target:
                return self._move_toward(
                    x,
                    y,
                    tx,
                    ty,
                )

            return ["HARVEST"]

        # ----------------------------------------------------
        # 2. CRITICAL WATER
        # ----------------------------------------------------

        target = self._best_water_target(
            farm.tiles,
            critical_only=True,
        )

        if target is not None:
            tx, ty = target

            if (x, y) != target:
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

        target = self._best_water_target(
            farm.tiles,
            critical_only=False,
        )

        if target is not None:
            tx, ty = target

            if (x, y) != target:
                return self._move_toward(
                    x,
                    y,
                    tx,
                    ty,
                )

            return ["WATER"]

        # ----------------------------------------------------
        # 4. RETURN HARVESTED WHEAT TO SHED
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
        # 5. PLANT NEXT SEED
        # ----------------------------------------------------

        seeds = int(
            state.private.seeds.get(
                self.CROP,
                0,
            )
        )

        if seeds > 0:

            target = self._best_plant_target(
                farm.tiles
            )

            if target is not None:
                tx, ty = target

                if (x, y) != target:
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
        # 6. NOTHING TO DO
        # ----------------------------------------------------

        return ["PASS"]

    # ========================================================
    # TASK SELECTION
    # ========================================================

    @classmethod
    def _best_harvest_target(cls, tiles):
        """Harvest any controlled cell at peak yield."""

        candidates = []

        for position in cls.PRODUCTION_TILES:

            tile = cls._tile_at(
                tiles,
                *position,
            )

            if not cls._is_wheat(tile):
                continue

            yield_units = int(
                tile.get("yield_units", 0)
            )

            if yield_units >= 4:
                candidates.append(
                    (
                        -yield_units,
                        position,
                    )
                )

        if not candidates:
            return None

        candidates.sort()

        return candidates[0][1]

    @classmethod
    def _best_water_target(
        cls,
        tiles,
        *,
        critical_only: bool,
    ):
        """
        Select the wheat tile requiring water.

        Critical crops (consecutive_unwatered >= 1)
        are prioritized first.
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
    def _best_plant_target(cls, tiles):
        """Return the first empty controlled cell."""

        for position in cls.PRODUCTION_TILES:

            tile = cls._tile_at(
                tiles,
                *position,
            )

            if tile is None:
                return position

        return None

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _tile_at(tiles, x: int, y: int):

        if y < 0 or y >= len(tiles):
            return None

        if x < 0 or x >= len(tiles[y]):
            return None

        return tiles[y][x]

    @staticmethod
    def _is_wheat(tile):

        return (
            isinstance(tile, dict)
            and tile.get("kind") == "PLANT"
            and tile.get("crop") == "WHEAT"
        )

    @staticmethod
    def _carried_wheat(state):

        if not state.private.inventories:
            return 0

        return int(
            state.private.inventories[0].get(
                "WHEAT",
                0,
            )
        )

    @staticmethod
    def _move_toward(
        x: int,
        y: int,
        tx: int,
        ty: int,
    ):

        if x < tx:
            return ["EAST"]

        if x > tx:
            return ["WEST"]

        if y < ty:
            return ["SOUTH"]

        if y > ty:
            return ["NORTH"]

        return ["PASS"]
