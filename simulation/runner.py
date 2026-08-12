
"""
Kaggriculture simulation runner.

V0 responsibility:
    Provide a small, reusable interface for running Kaggriculture
    games and collecting their results.

This module does NOT contain strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import json

from kaggle_environments import make


Agent = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class PlayerResult:
    """Final result for one player."""

    player: int
    reward: float | None
    status: str | None


@dataclass(frozen=True)
class SimulationResult:
    """Result of one complete simulation."""

    players: tuple[PlayerResult, ...]
    steps: int
    replay: dict[str, Any] | None = None

    @property
    def rewards(self) -> dict[int, float | None]:
        """Return final rewards indexed by player."""
        return {
            result.player: result.reward
            for result in self.players
        }

    @property
    def winner(self) -> int | None:
        """
        Return winning player.

        Returns None for a tie or unavailable rewards.
        """
        valid = [
            result
            for result in self.players
            if result.reward is not None
        ]

        if len(valid) != 2:
            return None

        if valid[0].reward == valid[1].reward:
            return None

        return max(
            valid,
            key=lambda result: result.reward
        ).player


class SimulationRunner:
    """Run local Kaggriculture simulations."""

    def __init__(
        self,
        episode_steps: int = 720,
        debug: bool = False,
    ) -> None:
        if episode_steps < 1:
            raise ValueError(
                "episode_steps must be >= 1"
            )

        self.episode_steps = episode_steps
        self.debug = debug

    def run(
        self,
        agent_a: Agent | str,
        agent_b: Agent | str,
        *,
        save_replay: bool = False,
        replay_path: str | Path | None = None,
    ) -> SimulationResult:
        """
        Run one Kaggriculture match.

        agent_a:
            Player 0 agent/function or Kaggle built-in name.

        agent_b:
            Player 1 agent/function or Kaggle built-in name.

        save_replay:
            Whether to serialize the replay.

        replay_path:
            Optional path for saved replay JSON.
        """

        env = make(
            "kaggriculture",
            configuration={
                "episodeSteps": self.episode_steps,
            },
            debug=self.debug,
        )

        env.run([
            agent_a,
            agent_b,
        ])

        final_step = env.steps[-1]

        results: list[PlayerResult] = []

        for player, state in enumerate(final_step):
            reward = getattr(state, "reward", None)
            status = getattr(state, "status", None)

            if reward is not None:
                reward = float(reward)

            results.append(
                PlayerResult(
                    player=player,
                    reward=reward,
                    status=status,
                )
            )

        replay = None

        if save_replay:
            replay = env.toJSON()

            if replay_path is not None:
                replay_path = Path(replay_path)
                replay_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                replay_path.write_text(
                    json.dumps(
                        replay,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

        return SimulationResult(
            players=tuple(results),
            steps=len(env.steps),
            replay=replay,
        )
