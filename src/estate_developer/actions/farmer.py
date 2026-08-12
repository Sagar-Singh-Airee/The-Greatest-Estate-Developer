
"""
V1 Reliable Farmer Executor.

Objective:
    Complete a controlled wheat production cycle reliably.

V1 intentionally manages ONE wheat production tile.

Cycle:
    buy seed
        ↓
    move to production tile
        ↓
    plant
        ↓
    water
        ↓
    maintain until peak
        ↓
    harvest
        ↓
    return to shed
        ↓
    place wheat into shed
"""

from __future__ import annotations

from estate_developer.state.parser import ObservationState


class ReliableFarmer:
    """Reliable single-wheat executor."""

    CROP = "WHEAT"

    # Starting farmer position is (4, 4).
    # This tile is immediately adjacent.
    TARGET_TILE = (3, 4)

    # One of the documented shed-access positions.
    SHED_TILE = (4, 4)

    def decide(
        self,
        state: ObservationState,
    ) -> list[str]:

        farm = state.me

        x = farm.farmer.x
        y = farm.farmer.y

        target_x, target_y = self.TARGET_TILE

        target_tile = self._tile_at(
            farm.tiles,
            target_x,
            target_y,
        )

        # ====================================================
        # 1. ACTIVE WHEAT
        # ====================================================

        if self._is_wheat(target_tile):

            # Water once per day when needed.
            if not target_tile.get(
                "watered_today",
                False,
            ):
                if (x, y) != self.TARGET_TILE:
                    return self._move_toward(
                        x,
                        y,
                        target_x,
                        target_y,
                    )

                return ["WATER"]

            # Harvest at the proven peak yield.
            if self._is_peak_wheat(target_tile):

                if (x, y) != self.TARGET_TILE:
                    return self._move_toward(
                        x,
                        y,
                        target_x,
                        target_y,
                    )

                return ["HARVEST"]

            # Stay close to the production tile.
            if (x, y) != self.TARGET_TILE:
                return self._move_toward(
                    x,
                    y,
                    target_x,
                    target_y,
                )

            return ["PASS"]

        # ====================================================
        # 2. HARVESTED WHEAT IN FARMER INVENTORY
        # ====================================================

        carried_wheat = self._carried_wheat(state)

        if carried_wheat > 0:

            if (x, y) != self.SHED_TILE:
                return self._move_toward(
                    x,
                    y,
                    self.SHED_TILE[0],
                    self.SHED_TILE[1],
                )

            # Proven working transfer mechanism.
            return [
                "PLACE",
                self.CROP,
                carried_wheat,
            ]

        # ====================================================
        # 3. PLANT NEXT SEED
        # ====================================================

        seed_count = state.private.seeds.get(
            self.CROP,
            0,
        )

        if seed_count > 0:

            if (x, y) != self.TARGET_TILE:
                return self._move_toward(
                    x,
                    y,
                    target_x,
                    target_y,
                )

            if target_tile is None:
                return [
                    "PLANT",
                    self.CROP,
                ]

        # ====================================================
        # 4. NOTHING TO DO
        # ====================================================

        return ["PASS"]

    # ========================================================
    # Helpers
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

    @classmethod
    def _is_peak_wheat(cls, tile) -> bool:
        """
        Harvest once wheat reaches the proven
        unfertilized peak yield of 4.
        """

        if not cls._is_wheat(tile):
            return False

        return tile.get(
            "yield_units",
            0,
        ) >= 4

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
