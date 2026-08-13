
"""
V3 Task-to-Action Bridge.

Converts existing V2 FarmTask objects into the simple action
format consumed by the V3 transition engine.

V2 remains untouched.
"""

from __future__ import annotations

from typing import Any

from estate_developer.planning.tasks import (
    FarmTask,
    TaskType,
)


def task_to_action(
    task: FarmTask,
) -> list[Any]:
    """
    Convert a V2 FarmTask into a hypothetical V3 action.
    """

    task_type = task.task_type

    if task_type == TaskType.PASS:

        return [
            "PASS",
        ]

    if task_type == TaskType.WATER:

        return [
            "WATER",
            task.crop,
            task.target,
        ]

    if task_type == TaskType.PLANT:

        return [
            "PLANT",
            task.crop,
            task.target,
        ]

    if task_type == TaskType.HARVEST:

        return [
            "HARVEST",
            task.crop,
            task.target,
        ]

    if task_type == TaskType.PLACE:

        return [
            "PLACE",
            task.crop,
            max(
                1,
                int(
                    task.quantity
                ),
            ),
        ]

    if task_type == TaskType.BUY_SEED:

        return [
            "BUY_SEED",
            task.crop,
            max(
                1,
                int(
                    task.quantity
                ),
            ),
        ]

    raise ValueError(
        f"Unsupported FarmTask: {task!r}"
    )


def task_label(
    task: FarmTask,
) -> str:
    """
    Return a compact human-readable planning label.
    """

    return (
        f"{task.task_type.value}"
        f":{task.crop or '-'}"
        f":{task.target or '-'}"
    )
