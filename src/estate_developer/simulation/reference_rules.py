
"""
V11 Reference Rules

Authoritative Kaggriculture mechanics mirrored from the installed
kaggriculture environment source used during development.

This module contains rules only.
No strategy, search, planning, or opponent logic.
"""

from __future__ import annotations

from copy import deepcopy
from math import log, log10, sqrt
from typing import Final


# ============================================================
# Episode / board configuration
# ============================================================

BOARD_SIZE: Final[int] = 10
STARTING_MONEY: Final[float] = 2000.0
TURNS_PER_DAY: Final[int] = 24
EPISODE_STEPS: Final[int] = 720
SHED_CAPACITY: Final[int] = 100

WEED_SPAWN_CHANCE: Final[float] = 0.005

TOWN_SHOP_UNLOCK_INTERVAL: Final[int] = 3
TOWN_SHOP_SELL_INTERVAL: Final[int] = 2
TOWN_CENTER_SELL_INTERVAL: Final[int] = 6

FARM_HAND_COST_MULT: Final[int] = 10
MAX_MARKET_ORDERS_PER_TURN: Final[int] = 10


# ============================================================
# Crops
# ============================================================

CROPS: Final[dict[str, dict[str, object]]] = {
    "WHEAT": {
        "seed": 10,
        "first_yield_day": 2,
        "max_yield_day": 4,
        "interval": 0,
        "max_yield": 6,
        "ongoing": False,
    },
    "CARROT": {
        "seed": 20,
        "first_yield_day": 2,
        "max_yield_day": 3,
        "interval": 0,
        "max_yield": 4,
        "ongoing": False,
    },
    "TOMATO": {
        "seed": 50,
        "first_yield_day": 8,
        "max_yield_day": 8,
        "interval": 1,
        "max_yield": 4,
        "ongoing": True,
    },
    "STRAWBERRY": {
        "seed": 100,
        "first_yield_day": 10,
        "max_yield_day": 10,
        "interval": 2,
        "max_yield": 4,
        "ongoing": True,
    },
    "MELON": {
        "seed": 80,
        "first_yield_day": 10,
        "max_yield_day": 12,
        "interval": 0,
        "max_yield": 6,
        "ongoing": False,
    },
}


# ============================================================
# Animals
# ============================================================

ANIMALS: Final[dict[str, dict[str, object]]] = {
    "GOOSE": {
        "cost": 300,
        "structure": "COOP",
        "first_yield_day": 4,
        "interval": 1,
        "max_held": 4,
        "product": "EGG",
    },
    "COW": {
        "cost": 600,
        "structure": "PASTURE",
        "first_yield_day": 8,
        "interval": 2,
        "max_held": 6,
        "product": "MILK",
    },
    "SHEEP": {
        "cost": 500,
        "structure": "PASTURE",
        "first_yield_day": 6,
        "interval": 3,
        "max_held": 6,
        "product": "WOOL",
    },
}


# ============================================================
# Products
# ============================================================

PRODUCTS: Final[tuple[str, ...]] = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)


# ============================================================
# Market
# ============================================================

MARKET_I0: Final[int] = 10000
PRICE_FLOOR: Final[int] = 1

MARKET_PARAMS: Final[dict[str, dict[str, object]]] = {
    "WHEAT": {
        "base": 25,
        "I0": 10000,
        "T": 400,
        "below_func": "sqrt",
        "below_target": 0.80,
        "above_func": "log",
        "above_target": 0.20,
    },
    "CARROT": {
        "base": 35,
        "I0": 10000,
        "T": 450,
        "below_func": "log",
        "below_target": 0.20,
        "above_func": "sqrt",
        "above_target": 0.70,
    },
    "TOMATO": {
        "base": 60,
        "I0": 10000,
        "T": 200,
        "below_func": "linear",
        "below_target": 0.40,
        "above_func": "sqrt",
        "above_target": 0.60,
    },
    "STRAWBERRY": {
        "base": 120,
        "I0": 10000,
        "T": 100,
        "below_func": "sqrt",
        "below_target": 0.70,
        "above_func": "linear",
        "above_target": 0.40,
    },
    "MELON": {
        "base": 250,
        "I0": 10000,
        "T": 300,
        "below_func": "log",
        "below_target": 0.20,
        "above_func": "sq",
        "above_target": 0.90,
    },
    "EGG": {
        "base": 50,
        "I0": 10000,
        "T": 332,
        "below_func": "linear",
        "below_target": 0.40,
        "above_func": "log",
        "above_target": 0.20,
    },
    "MILK": {
        "base": 160,
        "I0": 10000,
        "T": 122,
        "below_func": "sqrt",
        "below_target": 0.60,
        "above_func": "linear",
        "above_target": 0.40,
    },
    "WOOL": {
        "base": 200,
        "I0": 10000,
        "T": 105,
        "below_func": "log",
        "below_target": 0.20,
        "above_func": "sq",
        "above_target": 0.80,
    },
    "FERTILIZER": {
        "base": 100,
        "I0": 10000,
        "T": 200,
        "below_func": "linear",
        "below_target": 0.40,
        "above_func": "linear",
        "above_target": 0.40,
    },
}


# ============================================================
# Land
# ============================================================

LAND_ORDER: Final[tuple[str, ...]] = (
    "NE",
    "SW",
    "SE",
)

LAND_PRICES: Final[tuple[int, ...]] = (
    1000,
    2000,
    4000,
)


# ============================================================
# Town
# ============================================================

SHOPS: Final[dict[str, tuple[str, ...]]] = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": (
        "WHEAT",
        "CARROT",
        "TOMATO",
        "STRAWBERRY",
    ),
}

TOWN_CENTER_PRODUCTS: Final[tuple[str, ...]] = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
)

TOWN_CENTER_DEMAND_SCHEDULE: Final[tuple[tuple[int, int], ...]] = (
    (20, 4),
    (10, 2),
    (0, 1),
)


# ============================================================
# Market helpers
# ============================================================

def shape_value(func: str, x: float) -> float:
    x = max(0.0, float(x))

    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return sqrt(x)
    if func == "log":
        return log(1.0 + x)
    if func == "log10":
        return log10(1.0 + x)

    return x


def market_price(
    item: str,
    inventory: int,
    *,
    params: dict[str, dict[str, object]] | None = None,
) -> int:
    resolved = params if params is not None else MARKET_PARAMS
    p = resolved[item]

    base = float(p["base"])
    i0 = int(p["I0"])
    target = float(p["T"])

    if inventory < i0:
        func = str(p["below_func"])
        amp = (
            float(p["below_target"])
            * base
            / shape_value(func, target)
        )
        price = (
            base
            + amp * shape_value(func, i0 - inventory)
        )
    else:
        func = str(p["above_func"])
        amp = (
            float(p["above_target"])
            * base
            / shape_value(func, target)
        )
        price = (
            base
            - amp * shape_value(func, inventory - i0)
        )

    return max(
        PRICE_FLOOR,
        int(round(price)),
    )


def copy_rules() -> dict[str, object]:
    return deepcopy(
        {
            "crops": CROPS,
            "animals": ANIMALS,
            "products": PRODUCTS,
            "market_params": MARKET_PARAMS,
            "land_order": LAND_ORDER,
            "land_prices": LAND_PRICES,
            "shops": SHOPS,
            "town_center_products": TOWN_CENTER_PRODUCTS,
            "town_center_demand_schedule":
                TOWN_CENTER_DEMAND_SCHEDULE,
        }
    )


__all__ = [
    "BOARD_SIZE",
    "STARTING_MONEY",
    "TURNS_PER_DAY",
    "EPISODE_STEPS",
    "SHED_CAPACITY",
    "WEED_SPAWN_CHANCE",
    "TOWN_SHOP_UNLOCK_INTERVAL",
    "TOWN_SHOP_SELL_INTERVAL",
    "TOWN_CENTER_SELL_INTERVAL",
    "FARM_HAND_COST_MULT",
    "MAX_MARKET_ORDERS_PER_TURN",
    "CROPS",
    "ANIMALS",
    "PRODUCTS",
    "MARKET_I0",
    "PRICE_FLOOR",
    "MARKET_PARAMS",
    "LAND_ORDER",
    "LAND_PRICES",
    "SHOPS",
    "TOWN_CENTER_PRODUCTS",
    "TOWN_CENTER_DEMAND_SCHEDULE",
    "shape_value",
    "market_price",
    "copy_rules",
]
