
"""
V2.14.1 Transaction-Level Telemetry.

Events can now carry market transaction information so that
crop-level revenue can be reconstructed from actual gameplay.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventType(str, Enum):

    BUY_SEED = "BUY_SEED"
    BUY_PRODUCT = "BUY_PRODUCT"
    SELL = "SELL"

    PLANT = "PLANT"
    WATER = "WATER"
    HARVEST = "HARVEST"
    PLACE = "PLACE"

    MONEY_CHANGE = "MONEY_CHANGE"
    CROP_CREATED = "CROP_CREATED"
    CROP_REMOVED = "CROP_REMOVED"


@dataclass(frozen=True)
class FarmEvent:

    step: int
    day: int
    hour: int

    event_type: EventType

    crop: str | None = None

    quantity: int = 0

    money_delta: float = 0.0

    position: tuple[int, int] | None = None

    details: str = ""

    # --------------------------------------------------------
    # Market transaction telemetry
    # --------------------------------------------------------

    unit_price: float = 0.0

    gross_revenue: float = 0.0

    market_inventory_before: int | None = None

    market_inventory_after: int | None = None
