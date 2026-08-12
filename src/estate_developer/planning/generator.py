
"""
V1.3.1 Global Task Generator.

All immediate executable decisions originate here.
"""

from __future__ import annotations

from estate_developer.planning.tasks import (
    FarmTask,
    TaskType,
)


class TaskGenerator:

    BUY_SEED_PRIORITY = 500

    PLANT_PRIORITY = 600
    PLACE_PRIORITY = 700
    WATER_NORMAL_PRIORITY = 800
    WATER_CRITICAL_PRIORITY = 900
    HARVEST_PRIORITY = 1000

    CROP = "WHEAT"

    SEED_COST = 10

    def generate(
        self,
        state,
        *,
        max_active_wheat: int = 3,
    ) -> list[FarmTask]:

        tasks = []

        active_wheat = 0

        # ----------------------------------------------------
        # Scan farm
        # ----------------------------------------------------

        for y, row in enumerate(state.me.tiles):

            for x, tile in enumerate(row):

                if not isinstance(tile, dict):
                    continue

                if (
                    tile.get("kind") == "PLANT"
                    and tile.get("crop") == self.CROP
                ):

                    active_wheat += 1

                    yield_units = int(
                        tile.get(
                            "yield_units",
                            0,
                        )
                    )

                    # ----------------------------------------
                    # HARVEST
                    # ----------------------------------------

                    if yield_units >= 4:

                        tasks.append(
                            FarmTask(
                                task_type=TaskType.HARVEST,
                                priority=self.HARVEST_PRIORITY,
                                target=(x, y),
                                crop=self.CROP,
                                reason="wheat at peak yield",
                            )
                        )

                        continue

                    # ----------------------------------------
                    # WATER
                    # ----------------------------------------

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
                                "wheat nearing "
                                "watering failure"
                            )

                        else:

                            priority = (
                                self.WATER_NORMAL_PRIORITY
                            )

                            reason = (
                                "wheat requires "
                                "daily watering"
                            )

                        tasks.append(
                            FarmTask(
                                task_type=TaskType.WATER,
                                priority=priority,
                                target=(x, y),
                                crop=self.CROP,
                                reason=reason,
                            )
                        )

        # ----------------------------------------------------
        # PLACE harvested wheat
        # ----------------------------------------------------

        carried = 0

        if state.private.inventories:

            carried = int(
                state.private.inventories[0].get(
                    self.CROP,
                    0,
                )
            )

        if carried > 0:

            tasks.append(
                FarmTask(
                    task_type=TaskType.PLACE,
                    priority=self.PLACE_PRIORITY,
                    crop=self.CROP,
                    quantity=carried,
                    reason="transfer harvested wheat to shed",
                )
            )

        # ----------------------------------------------------
        # BUY SEED
        #
        # This is now part of the planning system.
        # ----------------------------------------------------

        seeds = int(
            state.private.seeds.get(
                self.CROP,
                0,
            )
        )

        shed = int(
            state.private.shed.get(
                self.CROP,
                0,
            )
        )

        if (
            active_wheat < max_active_wheat
            and seeds == 0
            and carried == 0
            and shed == 0
            and state.me.money >= self.SEED_COST
        ):

            tasks.append(
                FarmTask(
                    task_type=TaskType.BUY_SEED,
                    priority=self.BUY_SEED_PRIORITY,
                    crop=self.CROP,
                    quantity=1,
                    reason=(
                        "production capacity available "
                        "and no wheat seed held"
                    ),
                )
            )

        # ----------------------------------------------------
        # PLANT
        # ----------------------------------------------------

        if (
            seeds > 0
            and active_wheat < max_active_wheat
        ):

            target = self._find_empty_tile(
                state.me.tiles
            )

            if target is not None:

                tasks.append(
                    FarmTask(
                        task_type=TaskType.PLANT,
                        priority=self.PLANT_PRIORITY,
                        target=target,
                        crop=self.CROP,
                        quantity=1,
                        reason="unused production capacity",
                    )
                )

        # ----------------------------------------------------
        # FALLBACK
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

    @staticmethod
    def _find_empty_tile(tiles):

        preferred = (
            (3, 4),
            (2, 4),
            (3, 3),
        )

        for x, y in preferred:

            if (
                0 <= y < len(tiles)
                and 0 <= x < len(tiles[y])
                and tiles[y][x] is None
            ):
                return (x, y)

        return None
