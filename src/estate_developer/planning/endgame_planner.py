from __future__ import annotations

from typing import Any
from estate_developer.state.parser import ObservationState
from estate_developer.planning.generator import TaskGenerator
from estate_developer.planning.scheduler import TaskScheduler
from estate_developer.execution.hand_assignment import HandAssignmentSolver
from estate_developer.simulation.reference_rules import EPISODE_STEPS


class EndgamePlanner:
    """
    V10 True Endgame Planner.
    
    Instead of passing and selling everything, it keeps working!
    It filters out long-term investments (PLANT, BUY_SEED, BUILD_COOP, BUILD_PASTURE)
    but continues to HARVEST, WATER, FEED, and CARE.
    
    In the final 3 ticks, it dumps the entire inventory to the market.
    """

    def __init__(self):
        self.generator = TaskGenerator()
        self.scheduler = TaskScheduler()
        self.hand_solver = HandAssignmentSolver()

    def is_endgame(self, state: ObservationState, max_steps: int = EPISODE_STEPS) -> bool:
        """
        Determines if the game is entering the endgame window.
        
        EPISODE_STEPS = 720 (30 days × 24 hours).
        Endgame begins when fewer than 45 steps remain.
        """
        remaining = max_steps - state.step
        return remaining <= 45

    def plan_liquidation(self, state: ObservationState, max_steps: int = EPISODE_STEPS) -> list[dict[str, Any]]:
        """
        Generates a sequence of actions tailored for the endgame.
        """
        remaining = max_steps - state.step
        
        # 1. Generate normal tasks
        all_tasks = self.generator.generate(state)
        
        # 2. Filter out investments
        # We don't want to start anything new if we can't harvest it
        banned_types = {"PLANT", "BUY_SEED", "BUILD_COOP", "BUILD_PASTURE", "FERTILIZE"}
        
        # If very close to end, also stop caring/feeding as it won't yield
        if remaining <= 10:
            banned_types.update({"CARE", "FEED", "COLLECT_FERTILIZER"})
            
        allowed_tasks = [
            t for t in all_tasks 
            if t.task_type.value not in banned_types
        ]
        
        # 3. Pick top task for farmer
        if not allowed_tasks:
            from estate_developer.planning.tasks import FarmTask, TaskType
            allowed_tasks = [FarmTask(task_type=TaskType.PASS, priority=0)]
            
        farmer_task = allowed_tasks[0]
        farmer_action = self.scheduler.farmer_action(farmer_task, state)
        
        # 4. Assign hands
        remaining_tasks = allowed_tasks[1:]
        hand_actions = self.hand_solver.assign(state, remaining_tasks)
        
        # 5. Market dumping
        market_actions = []
        
        # In the final 3 ticks, or if shed is totally full, sell everything
        shed = state.private.shed
        shed_count = sum(v for v in shed.values() if isinstance(v, (int, float)))
        
        if remaining <= 3 or shed_count > 90:
            for item, qty in shed.items():
                if qty > 0:
                    market_actions.append(["SELL", item, qty])
        
        # Return as a single-step trajectory
        return [{
            "farmer": farmer_action,
            "hands": hand_actions,
            "market": market_actions[:10]
        }]
