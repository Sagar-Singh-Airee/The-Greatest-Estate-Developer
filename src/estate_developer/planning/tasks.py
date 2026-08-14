
"""
V1.3.1 task model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):

    BUY_SEED = "BUY_SEED"
    BUY_ANIMAL = "BUY_ANIMAL"
    HIRE = "HIRE"
    BUY_LAND = "BUY_LAND"
    HARVEST = "HARVEST"
    WATER = "WATER"
    PLACE = "PLACE"
    PLANT = "PLANT"
    BUILD_COOP = "BUILD_COOP"
    BUILD_PASTURE = "BUILD_PASTURE"
    DIG = "DIG"
    FERTILIZE = "FERTILIZE"
    FEED = "FEED"
    CARE = "CARE"
    COLLECT_FERTILIZER = "COLLECT_FERTILIZER"
    PASS = "PASS"


@dataclass(frozen=True)
class FarmTask:

    task_type: TaskType
    priority: int

    target: tuple[int, int] | None = None

    crop: str | None = None

    quantity: int = 0

    reason: str = ""
