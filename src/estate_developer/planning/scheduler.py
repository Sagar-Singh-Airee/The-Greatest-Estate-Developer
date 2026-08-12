
"""
V1.3.1 task scheduler.

Separates:
    farmer operations
    from
    market operations
"""

from __future__ import annotations

from estate_developer.planning.tasks import (
    FarmTask,
    TaskType,
)


class TaskScheduler:

    SHED_TILES = (
        (4, 4),
        (5, 4),
        (4, 5),
        (5, 5),
    )

    def choose(
        self,
        tasks: list[FarmTask],
    ) -> FarmTask:

        if not tasks:

            return FarmTask(
                task_type=TaskType.PASS,
                priority=0,
                reason="empty task list",
            )

        return max(
            tasks,
            key=lambda task: task.priority,
        )

    def farmer_action(
        self,
        task: FarmTask,
        state,
    ) -> list[str]:

        x = state.me.farmer.x
        y = state.me.farmer.y

        # BUY_SEED is a market task.
        if task.task_type == TaskType.BUY_SEED:
            return ["PASS"]

        if task.task_type == TaskType.PASS:
            return ["PASS"]

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

    @classmethod
    def _nearest_shed_tile(
        cls,
        x: int,
        y: int,
    ):

        return min(
            cls.SHED_TILES,
            key=lambda pos:
                abs(x - pos[0])
                + abs(y - pos[1]),
        )
