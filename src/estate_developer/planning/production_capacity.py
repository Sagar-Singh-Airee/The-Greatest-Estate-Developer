"""
V2.42 Dynamic Production Capacity.

This module owns physical production-tile discovery.

It does NOT decide how many tiles should be economically used.

It answers:

    Which unlocked farm tiles are available for production?

Verified Kaggriculture tile semantics:

    None       -> unlocked empty tile
    "LOCKED"   -> unavailable tile
    dict       -> occupied/special structure

The validated V2.41 production positions remain first in the
ordering so that dynamic discovery preserves existing behavior.
"""

from __future__ import annotations

from typing import Any


PREFERRED_PRODUCTION_TILES = (
    (3, 4),
    (2, 4),
    (3, 3),
    (2, 3),
    (1, 3),
    (1, 2),
    (0, 2),
)


def discover_production_tiles(
    tiles: list[list[Any]],
) -> tuple[tuple[int, int], ...]:
    """
    Return all currently unlocked and empty farm tiles.

    Preferred validated production positions are returned first.
    All remaining empty unlocked positions follow in board order.
    """

    discovered: list[tuple[int, int]] = []

    preferred = set(
        PREFERRED_PRODUCTION_TILES
    )

    # --------------------------------------------------------
    # Preserve the validated V2.41 ordering.
    # --------------------------------------------------------

    for x, y in PREFERRED_PRODUCTION_TILES:

        if (
            0 <= y < len(tiles)
            and 0 <= x < len(tiles[y])
            and tiles[y][x] is None
        ):
            discovered.append(
                (x, y)
            )

    # --------------------------------------------------------
    # Add every other unlocked empty tile.
    # --------------------------------------------------------

    for y, row in enumerate(tiles):

        for x, tile in enumerate(row):

            if (
                tile is None
                and (x, y) not in preferred
            ):
                discovered.append(
                    (x, y)
                )

    return tuple(
        discovered
    )


def count_active_production(
    tiles: list[list[Any]],
) -> int:
    """
    Count active plant structures across the entire farm.

    Physical production capacity is independent from the
    economic utilization ceiling.
    """

    count = 0

    for row in tiles:

        for tile in row:

            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
            ):
                count += 1

    return count
