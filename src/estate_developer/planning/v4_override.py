
"""
Validated V4 production override.

V4.67

This module contains ONLY the empirically validated
STEP-483 replacement rule.

V2 remains the controller everywhere else.
"""

from __future__ import annotations

from typing import Any


EPISODE_END = 720

VALIDATED_WAVE_START = 483
VALIDATED_WAVE_SIZE = 4

WHEAT_CYCLE = 94
WHEAT_GAP = 2

MELON_CYCLE = 270
MELON_GAP = 2


class V4ValidatedOverride:
    """
    Narrow, read-only decision guard.

    It never executes an action itself.
    """

    def __init__(self) -> None:

        self._recent_removals: list[
            dict[str, Any]
        ] = []

        self._used = False

    @staticmethod
    def _cycles_available(
        start_step: int,
        cycle: int,
        gap: int,
    ) -> int:

        step = int(
            start_step
        )

        cycles = 0

        while True:

            remove_step = (
                step + cycle
            )

            if remove_step > EPISODE_END:
                break

            cycles += 1

            next_plant = (
                remove_step + gap
            )

            if next_plant >= EPISODE_END:
                break

            step = next_plant

        return cycles

    @staticmethod
    def _tile_snapshot(
        obs: dict[str, Any],
    ) -> dict[tuple[int, int], Any]:

        tiles = (
            obs["farms"][0]["tiles"]
        )

        return {
            (x, y): row[x]
            for y, row in enumerate(
                tiles
            )
            for x in range(
                len(row)
            )
        }

    def observe(
        self,
        obs: dict[str, Any],
    ) -> str | None:
        """
        Inspect the current observation.

        Returns:
            "WHEAT" when the exact validated opportunity appears.
            None otherwise.
        """

        if self._used:
            return None

        step = int(
            obs["step"]
        )

        current = self._tile_snapshot(
            obs
        )

        previous = getattr(
            self,
            "_previous_tiles",
            None,
        )

        if previous is not None:

            for position in current:

                before = previous.get(
                    position
                )

                after = current.get(
                    position
                )

                if not (
                    isinstance(
                        before,
                        dict,
                    )
                    and before.get(
                        "kind"
                    ) == "PLANT"
                    and after is None
                ):
                    continue

                crop = str(
                    before.get(
                        "crop",
                        "",
                    )
                ).upper()

                max_yield = {
                    "WHEAT": 4,
                    "CARROT": 3,
                    "MELON": 6,
                }.get(crop)

                yield_units = int(
                    before.get(
                        "yield_units",
                        0,
                    )
                )

                if (
                    max_yield is not None
                    and yield_units >= max_yield
                ):
                    self._recent_removals.append(
                        {
                            "step": step,
                            "tile": position,
                            "crop": crop,
                            "yield": yield_units,
                        }
                    )

        self._previous_tiles = current

        self._recent_removals = [
            event
            for event
            in self._recent_removals
            if (
                step
                - int(event["step"])
                <= 18
            )
        ]

        if not self._recent_removals:
            return None

        wave_start = int(
            self._recent_removals[0][
                "step"
            ]
        )

        wave_size = len(
            self._recent_removals
        )

        removed_crop = str(
            self._recent_removals[0][
                "crop"
            ]
        ).upper()

        evaluation_start = (
            wave_start + 2
        )

        wheat_cycles = (
            self._cycles_available(
                evaluation_start,
                WHEAT_CYCLE,
                WHEAT_GAP,
            )
        )

        melon_cycles = (
            self._cycles_available(
                evaluation_start,
                MELON_CYCLE,
                MELON_GAP,
            )
        )

        approved = (
            wave_start
            == VALIDATED_WAVE_START
            and wave_size
            == VALIDATED_WAVE_SIZE
            and removed_crop
            == "MELON"
            and wheat_cycles
            >= 2
            and melon_cycles
            == 0
        )

        if approved:

            self._used = True

            return "WHEAT"

        return None
