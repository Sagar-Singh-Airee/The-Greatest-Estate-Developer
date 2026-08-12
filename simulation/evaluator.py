
"""
Kaggriculture multi-match evaluator.

V0 responsibility:
    Run many simulations and summarize performance.

This module does NOT contain strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .runner import Agent, SimulationRunner


@dataclass(frozen=True)
class EvaluationResult:
    """Aggregate results from multiple matches."""

    games: int
    wins: int
    losses: int
    ties: int

    win_rate: float

    average_reward: float
    minimum_reward: float
    maximum_reward: float

    average_opponent_reward: float

    @property
    def loss_rate(self) -> float:
        """Return loss percentage as a decimal."""
        if self.games == 0:
            return 0.0

        return self.losses / self.games

    @property
    def tie_rate(self) -> float:
        """Return tie percentage as a decimal."""
        if self.games == 0:
            return 0.0

        return self.ties / self.games

    def summary(self) -> str:
        """Human-readable evaluation summary."""

        return (
            f"Games: {self.games}\n"
            f"Wins: {self.wins}\n"
            f"Losses: {self.losses}\n"
            f"Ties: {self.ties}\n"
            f"Win rate: {self.win_rate:.2%}\n"
            f"Average reward: {self.average_reward:.2f}\n"
            f"Minimum reward: {self.minimum_reward:.2f}\n"
            f"Maximum reward: {self.maximum_reward:.2f}\n"
            f"Average opponent reward: "
            f"{self.average_opponent_reward:.2f}"
        )


class Evaluator:
    """Evaluate an agent over multiple independent matches."""

    def __init__(
        self,
        episode_steps: int = 720,
        debug: bool = False,
    ) -> None:
        self.runner = SimulationRunner(
            episode_steps=episode_steps,
            debug=debug,
        )

    def evaluate(
        self,
        agent: Agent | str,
        opponent: Agent | str,
        *,
        games: int = 10,
    ) -> EvaluationResult:
        """
        Run multiple matches.

        The supplied agent always plays as Player 0.
        """

        if games < 1:
            raise ValueError("games must be >= 1")

        rewards: list[float] = []
        opponent_rewards: list[float] = []

        wins = 0
        losses = 0
        ties = 0

        for game_index in range(games):
            result = self.runner.run(
                agent,
                opponent,
            )

            player_reward = result.rewards.get(0)
            opponent_reward = result.rewards.get(1)

            if player_reward is None or opponent_reward is None:
                raise RuntimeError(
                    f"Game {game_index + 1} produced "
                    "missing rewards."
                )

            rewards.append(float(player_reward))
            opponent_rewards.append(float(opponent_reward))

            if player_reward > opponent_reward:
                wins += 1
            elif player_reward < opponent_reward:
                losses += 1
            else:
                ties += 1

        games_completed = len(rewards)

        return EvaluationResult(
            games=games_completed,
            wins=wins,
            losses=losses,
            ties=ties,
            win_rate=wins / games_completed,
            average_reward=sum(rewards) / games_completed,
            minimum_reward=min(rewards),
            maximum_reward=max(rewards),
            average_opponent_reward=(
                sum(opponent_rewards) / games_completed
            ),
        )
