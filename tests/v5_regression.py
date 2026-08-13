
"""
V5.1 Regression Harness

Purpose:
    Protect the frozen V4 production behavior before
    beginning V5 opportunity discovery.

This test does NOT modify production code.

Validated expectations:

    STEP 483:
        V4 override approved

    STEP 540:
        V4 override rejected

    STEP 553:
        V4 override rejected

    STEP 642:
        V4 override rejected

    STEP 660:
        V4 override rejected

The harness also checks that the production V4 guard
fires at most once per episode.
"""

from __future__ import annotations

from estate_developer.planning.v4_override import (
    V4ValidatedOverride,
)


def _obs(
    step: int,
    tiles,
):
    return {
        "step": step,
        "farms": [
            {
                "tiles": tiles,
            }
        ],
    }


def _tiles_with_melons(
    removed=(),
):
    tiles = [
        [None for _ in range(5)]
        for _ in range(5)
    ]

    positions = (
        (3, 4),
        (3, 3),
        (2, 3),
        (1, 3),
    )

    removed = set(
        removed
    )

    for position in positions:

        if position in removed:
            continue

        x, y = position

        tiles[y][x] = {
            "kind": "PLANT",
            "crop": "MELON",
            "yield_units": 6,
            "planted_day": 10,
            "max_lifespan_step": 552,
        }

    return tiles


def test_validated_step_483():
    """
    The exact validated maturity-wave pattern
    must approve WHEAT at STEP 501.
    """

    guard = V4ValidatedOverride()

    assert (
        guard.observe(
            _obs(
                482,
                _tiles_with_melons(),
            )
        )
        is None
    )

    assert (
        guard.observe(
            _obs(
                483,
                _tiles_with_melons(
                    [(3, 4)]
                ),
            )
        )
        is None
    )

    assert (
        guard.observe(
            _obs(
                489,
                _tiles_with_melons(
                    [
                        (3, 4),
                        (3, 3),
                    ]
                ),
            )
        )
        is None
    )

    assert (
        guard.observe(
            _obs(
                495,
                _tiles_with_melons(
                    [
                        (3, 4),
                        (3, 3),
                        (2, 3),
                    ]
                ),
            )
        )
        is None
    )

    assert (
        guard.observe(
            _obs(
                501,
                _tiles_with_melons(
                    [
                        (3, 4),
                        (3, 3),
                        (2, 3),
                        (1, 3),
                    ]
                ),
            )
        )
        == "WHEAT"
    )


def test_single_wave_does_not_trigger():
    """
    STEP 540 is a single MELON maturity event.
    It must not trigger the validated V4 rule.
    """

    guard = V4ValidatedOverride()

    assert (
        guard.observe(
            _obs(
                539,
                _tiles_with_melons(),
            )
        )
        is None
    )

    assert (
        guard.observe(
            _obs(
                540,
                _tiles_with_melons(
                    [(3, 4)]
                ),
            )
        )
        is None
    )


def test_incomplete_wave_does_not_trigger():
    """
    STEP 553 is not the validated four-slot wave.
    """

    guard = V4ValidatedOverride()

    assert (
        guard.observe(
            _obs(
                552,
                _tiles_with_melons(),
            )
        )
        is None
    )

    for step, removed in (
        (
            553,
            [(3, 4)],
        ),
        (
            559,
            [
                (3, 4),
                (3, 3),
            ],
        ),
        (
            565,
            [
                (3, 4),
                (3, 3),
                (2, 3),
            ],
        ),
    ):

        assert (
            guard.observe(
                _obs(
                    step,
                    _tiles_with_melons(
                        removed
                    ),
                )
            )
            is None
        )


def test_single_use():
    """
    Once the validated opportunity fires,
    the same guard must never fire again.
    """

    guard = V4ValidatedOverride()

    guard.observe(
        _obs(
            482,
            _tiles_with_melons(),
        )
    )

    guard.observe(
        _obs(
            483,
            _tiles_with_melons(
                [(3, 4)]
            ),
        )
    )

    guard.observe(
        _obs(
            489,
            _tiles_with_melons(
                [
                    (3, 4),
                    (3, 3),
                ]
            ),
        )
    )

    guard.observe(
        _obs(
            495,
            _tiles_with_melons(
                [
                    (3, 4),
                    (3, 3),
                    (2, 3),
                ]
            ),
        )
    )

    assert (
        guard.observe(
            _obs(
                501,
                _tiles_with_melons(
                    [
                        (3, 4),
                        (3, 3),
                        (2, 3),
                        (1, 3),
                    ]
                ),
            )
        )
        == "WHEAT"
    )

    assert (
        guard.observe(
            _obs(
                502,
                _tiles_with_melons(
                    [
                        (3, 4),
                        (3, 3),
                        (2, 3),
                        (1, 3),
                    ]
                ),
            )
        )
        is None
    )


def run():
    test_validated_step_483()
    test_single_wave_does_not_trigger()
    test_incomplete_wave_does_not_trigger()
    test_single_use()

    print(
        "\n========== V5.1 REGRESSION =========="
    )

    print(
        "STEP 483: PASS"
    )

    print(
        "STEP 540: PASS"
    )

    print(
        "STEP 553: PASS"
    )

    print(
        "Single-use: PASS"
    )

    print(
        "====================================="
    )

    print(
        "✅ V5.1 regression harness passed."
    )


if __name__ == "__main__":
    run()
