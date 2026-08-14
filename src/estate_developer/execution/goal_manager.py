from __future__ import annotations

from typing import Any
from estate_developer.state.parser import ObservationState
from estate_developer.planning.tasks import FarmTask

class GoalManager:
    """
    Maintains persistent goals for the farmer and hands across multiple ticks
    to prevent oscillation.
    """

    def __init__(self):
        self.active_goals: dict[int, FarmTask] = {}  # agent_id (0 for farmer, 1+ for hands) to Task
        
    def get_goal(self, agent_id: int) -> FarmTask | None:
        return self.active_goals.get(agent_id)
        
    def set_goal(self, agent_id: int, task: FarmTask) -> None:
        self.active_goals[agent_id] = task
        
    def clear_goal(self, agent_id: int) -> None:
        if agent_id in self.active_goals:
            del self.active_goals[agent_id]
            
    def update_goals(self, state: ObservationState) -> None:
        """
        Verify that active goals are still valid, and clear them if not.
        """
        # E.g., if a crop was harvested by someone else, clear the harvest goal.
        pass
