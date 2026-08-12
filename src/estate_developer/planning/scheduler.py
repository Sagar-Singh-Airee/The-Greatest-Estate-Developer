
"""
V1.4 Value-Aware Task Scheduler.

Instead of relying only on fixed task priorities, V1.4
scores each task using:

    urgency
    + economic value
    + quantity
    + failure risk
    - movement cost

Safety remains dominant:
    avoiding crop failure is more important than marginal
    revenue optimization.

This is still an execution scheduler.

It does NOT perform:
    - market forecasting
    - investment analysis
    - opponent modelling
    - land optimisation
"""

from __future__ import annotations

from estate_developer.planning.tasks import (
    FarmTask,
    TaskType,
)


class TaskScheduler:
    """Select the most useful currently executable task."""

    SHED_TILES = (
        (4, 4),
        (5, 4),
        (4, 5),
        (5, 5),
    )

    # --------------------------------------------------------
    # Safety weights
    # --------------------------------------------------------

    HARVEST_BASE = 1000

    WATER_CRITICAL_BASE = 1800
    WATER_NORMAL_BASE = 950

    PLACE_BASE = 700

    PLANT_BASE = 600

    BUY_SEED_BASE = 500

    PASS_BASE = 0

    # --------------------------------------------------------
    # Economic scaling
    # --------------------------------------------------------

    # Keep economic influence deliberately small in V1.4.
    # We are improving scheduling, not turning this into V2.
    VALUE_WEIGHT = 2.0

    # Movement has a real opportunity cost because the farmer
    # can only perform one operation per turn.
    MOVE_COST_PER_STEP = 4.0

    # Strong penalty for tasks requiring several moves.
    LONG_ROUTE_PENALTY = 1.0

    # ========================================================
    # TASK SELECTION
    # ========================================================

    def choose(
        self,
        tasks: list[FarmTask],
        state,
    ) -> FarmTask:

        if not tasks:

            return FarmTask(
                task_type=TaskType.PASS,
                priority=self.PASS_BASE,
                reason="empty task list",
            )

        scored = []

        for task in tasks:

            score = self.score(
                task,
                state,
            )

            scored.append(
                (
                    score,
                    task,
                )
            )

        # Deterministic tie breaking:
        # preserve the generator's existing priority and then
        # prefer the task with the higher raw priority.
        scored.sort(
            key=lambda item: (
                item[0],
                item[1].priority,
            ),
            reverse=True,
        )

        return scored[0][1]

    # ========================================================
    # SCORING
    # ========================================================

    def score(
        self,
        task: FarmTask,
        state,
    ) -> float:
        """
        Compute task utility.

        Safety dominates.
        Economic value only breaks relatively safe choices.
        """

        x = state.me.farmer.x
        y = state.me.farmer.y

        score = float(
            task.priority
        )

        # ----------------------------------------------------
        # HARD SAFETY / URGENCY
        # ----------------------------------------------------

        if task.task_type == TaskType.WATER:

            tile = self._tile_at(
                state.me.tiles,
                *(task.target or (x, y)),
            )

            unwatered = 0

            if isinstance(tile, dict):
                unwatered = int(
                    tile.get(
                        "consecutive_unwatered",
                        0,
                    )
                )

            if unwatered >= 1:

                # Critical watering should dominate almost
                # every non-critical task.
                score = max(
                    score,
                    self.WATER_CRITICAL_BASE,
                )

                score += 500 * unwatered

            else:

                score = max(
                    score,
                    self.WATER_NORMAL_BASE,
                )

        # ----------------------------------------------------
        # HARVEST VALUE
        # ----------------------------------------------------

        elif task.task_type == TaskType.HARVEST:

            tile = self._tile_at(
                state.me.tiles,
                *(task.target or (x, y)),
            )

            yield_units = 1

            if isinstance(tile, dict):
                yield_units = max(
                    1,
                    int(
                        tile.get(
                            "yield_units",
                            1,
                        )
                    ),
                )

            market_price = float(
                state.market.prices.get(
                    task.crop or "WHEAT",
                    0,
                )
            )

            economic_value = (
                yield_units * market_price
            )

            score += (
                self.VALUE_WEIGHT
                * economic_value
            )

        # ----------------------------------------------------
        # PLACE VALUE
        # ----------------------------------------------------

        elif task.task_type == TaskType.PLACE:

            market_price = float(
                state.market.prices.get(
                    task.crop or "WHEAT",
                    0,
                )
            )

            economic_value = (
                max(1, task.quantity)
                * market_price
            )

            score += (
                self.VALUE_WEIGHT
                * 0.5
                * economic_value
            )

        # ----------------------------------------------------
        # PLANT
        # ----------------------------------------------------

        elif task.task_type == TaskType.PLANT:

            market_price = float(
                state.market.prices.get(
                    task.crop or "WHEAT",
                    0,
                )
            )

            # Small forward-looking value signal.
            score += (
                self.VALUE_WEIGHT
                * 0.25
                * market_price
            )

        # ----------------------------------------------------
        # BUY SEED
        # ----------------------------------------------------

        elif task.task_type == TaskType.BUY_SEED:

            # Buying itself has no direct revenue. Keep the
            # action useful but below execution-critical work.
            score += 0.0

        # ----------------------------------------------------
        # MOVEMENT COST
        # ----------------------------------------------------

        distance = self._task_distance(
            x,
            y,
            task,
        )

        score -= (
            distance
            * self.MOVE_COST_PER_STEP
            * self.LONG_ROUTE_PENALTY
        )

        return score

    # ========================================================
    # DISTANCE
    # ========================================================

    def _task_distance(
        self,
        x: int,
        y: int,
        task: FarmTask,
    ) -> int:

        if task.task_type == TaskType.PLACE:

            target = self._nearest_shed_tile(
                x,
                y,
            )

            return (
                abs(x - target[0])
                + abs(y - target[1])
            )

        if task.target is None:
            return 0

        return (
            abs(x - task.target[0])
            + abs(y - task.target[1])
        )

    # ========================================================
    # FARMER ACTION
    # ========================================================

    def farmer_action(
        self,
        task: FarmTask,
        state,
    ) -> list[str]:

        x = state.me.farmer.x
        y = state.me.farmer.y

        # BUY_SEED is market-only.
        if task.task_type == TaskType.BUY_SEED:
            return ["PASS"]

        if task.task_type == TaskType.PASS:
            return ["PASS"]

        # ----------------------------------------------------
        # PLACE
        # ----------------------------------------------------

        if task.task_type == TaskType.PLACE:

            target = self._nearest_shed_tile(
                x,
                y,
            )

            if (x, y) != target:

                return self._move_toward(
                    x,
                    y,
                    target[0],
                    target[1],
                )

            return [
                "PLACE",
                task.crop,
                max(
                    1,
                    task.quantity,
                ),
            ]

        # ----------------------------------------------------
        # Tile task
        # ----------------------------------------------------

        if task.target is None:
            return ["PASS"]

        tx, ty = task.target

        if (x, y) != (tx, ty):

            return self._move_toward(
                x,
                y,
                tx,
                ty,
            )

        if task.task_type == TaskType.HARVEST:
            return ["HARVEST"]

        if task.task_type == TaskType.WATER:
            return ["WATER"]

        if task.task_type == TaskType.PLANT:
            return [
                "PLANT",
                task.crop,
            ]

        return ["PASS"]

    # ========================================================
    # HELPERS
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

    @classmethod
    def _nearest_shed_tile(
        cls,
        x: int,
        y: int,
    ) -> tuple[int, int]:

        return min(
            cls.SHED_TILES,
            key=lambda pos: (
                abs(x - pos[0])
                + abs(y - pos[1])
            ),
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
