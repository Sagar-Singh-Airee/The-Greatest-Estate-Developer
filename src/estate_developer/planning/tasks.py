
"""
V1.3.1 task model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):

    BUY_SEED = "BUY_SEED"
    HARVEST = "HARVEST"
    WATER = "WATER"
    PLACE = "PLACE"
    PLANT = "PLANT"
    PASS = "PASS"


@dataclass(frozen=True)
class FarmTask:

    task_type: TaskType
    priority: int

    target: tuple[int, int] | None = None

    crop: str | None = None

    quantity: int = 0

    reason: str = ""
