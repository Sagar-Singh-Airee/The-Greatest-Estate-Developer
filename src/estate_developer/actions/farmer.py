
"""
V1.3 scheduler-based farmer.

The farmer no longer has crop-specific branching for every
production tile.

Instead:

    Observation
        ↓
    TaskGenerator
        ↓
    TaskScheduler
        ↓
    One legal farmer action
"""

from __future__ import annotations

from estate_developer.planning.generator import TaskGenerator
from estate_developer.planning.scheduler import TaskScheduler


class ReliableFarmer:
    """Global farm task executor."""

    def __init__(self) -> None:

        self.generator = TaskGenerator()
        self.scheduler = TaskScheduler()

    def decide(
        self,
        state,
    ) -> list[str]:

        tasks = self.generator.generate(
            state,
            max_active_wheat=3,
        )

        selected = self.scheduler.choose(
            tasks
        )

        return self.scheduler.action_for(
            selected,
            state,
        )
