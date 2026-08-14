"""
The-Greatest-Estate-Developer.

V7 Trajectory-based Competitive Agent.

Architecture:

    Observation
        ↓
    Opponent Model Update
        ↓
    Strategic Trajectory Planner (Simulation + Search)
        ↓
    Action Sequence Output
"""

from __future__ import annotations

from typing import Any

from estate_developer.state.parser import ObservationParser
from estate_developer.opponent.opponent_model import OpponentModel
from estate_developer.strategic.trajectory_planner import StrategicTrajectoryPlanner


class EstateDeveloperAgent:

    def __init__(self):
        self.parser = ObservationParser()
        self.opponent_model = OpponentModel()
        self.planner = StrategicTrajectoryPlanner()

    def step(
        self,
        obs: dict[str, Any],
    ) -> dict[str, Any]:

        # Parse observation
        state = self.parser.parse(obs)

        # Update opponent model
        self.opponent_model.update(state)

        # Plan the next actions using trajectory search
        next_actions = self.planner.plan(state, self.opponent_model)

        return next_actions


_agent = EstateDeveloperAgent()


def agent(
    obs: dict[str, Any],
) -> dict[str, Any]:

    return _agent.step(obs)
