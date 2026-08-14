from __future__ import annotations

import math
from typing import Any
from estate_developer.state.parser import ObservationState, Position
from estate_developer.planning.tasks import FarmTask
from estate_developer.execution.pathfinder import Pathfinder


class HandAssignmentSolver:
    """
    Globally optimizes the assignment of tasks to farm hands to minimize movement
    using the Hungarian Algorithm.
    """

    def __init__(self):
        self.pathfinder = Pathfinder()

    def assign(self, state: ObservationState, available_tasks: list[FarmTask]) -> list[list[Any]]:
        """
        Assigns tasks to hands optimally. Returns a list of actions, one for each hand.
        """
        hands = state.me.hands
        actions = []

        if not hands:
            return []

        # Hands cannot autonomously collect a matching input from the shed.
        # Reserve feed, fertilizer, and placement logistics for the farmer,
        # who has a stateful pickup route; otherwise hands walk to a target
        # and repeatedly issue no-op actions.
        hand_safe = {
            "HARVEST",
            "WATER",
            "CARE",
            "COLLECT_FERTILIZER",
        }
        tasks = [
            task
            for task in available_tasks
            if task.target is not None and task.task_type.value in hand_safe
        ]

        if not tasks:
            return [["PASS"] for _ in hands]

        try:
            import numpy as np
            from scipy.optimize import linear_sum_assignment
            has_scipy = True
        except ImportError:
            has_scipy = False

        if has_scipy:
            # Build cost matrix: rows = hands, cols = tasks
            # We want to minimize distance, but also prioritize high-priority tasks.
            # Cost = distance - (task_priority * 100)
            cost_matrix = np.zeros((len(hands), len(tasks)))
            paths = {}  # Store paths to avoid recomputing

            for i, hand_pos in enumerate(hands):
                for j, task in enumerate(tasks):
                    target_pos = Position(task.target[0], task.target[1])
                    path = self.pathfinder.find_path(state, hand_pos, target_pos)
                    
                    if path:
                        dist = len(path) - 1
                        paths[(i, j)] = path
                    else:
                        dist = 999999
                        paths[(i, j)] = []

                    # We negate priority heavily so the solver picks the highest priority tasks first
                    # while minimizing distance among them.
                    cost = dist - (task.priority * 100)
                    cost_matrix[i, j] = cost

            row_ind, col_ind = linear_sum_assignment(cost_matrix)

            for i in range(len(hands)):
                if i in row_ind:
                    # Find which task this hand was assigned to
                    idx = list(row_ind).index(i)
                    j = col_ind[idx]
                    task = tasks[j]
                    path = paths[(i, j)]

                    if not path:
                        actions.append(["PASS"])
                        continue

                    hand_pos = hands[i]
                    if len(path) <= 1:
                        # At target, execute action
                        if task.task_type.value == "HARVEST":
                            actions.append(["HARVEST", task.target[0], task.target[1]])
                        elif task.task_type.value == "WATER":
                            actions.append(["WATER", task.target[0], task.target[1]])
                        elif task.task_type.value == "PLANT":
                            actions.append(["PLANT", task.crop, task.target[0], task.target[1]])
                        elif task.task_type.value == "FERTILIZE":
                            actions.append(["FERTILIZE", task.target[0], task.target[1]])
                        elif task.task_type.value == "FEED":
                            actions.append(["FEED", task.target[0], task.target[1]])
                        elif task.task_type.value == "CARE":
                            actions.append(["CARE", task.target[0], task.target[1]])
                        elif task.task_type.value == "COLLECT_FERTILIZER":
                            actions.append(["COLLECT_FERTILIZER", task.target[0], task.target[1]])
                        elif task.task_type.value == "PLACE":
                            actions.append(["PLACE", task.crop, 1])
                        else:
                            actions.append(["PASS"])
                    else:
                        # Move
                        next_pos = path[1]
                        if next_pos.x > hand_pos.x:
                            actions.append(["EAST"])
                        elif next_pos.x < hand_pos.x:
                            actions.append(["WEST"])
                        elif next_pos.y > hand_pos.y:
                            actions.append(["SOUTH"])
                        elif next_pos.y < hand_pos.y:
                            actions.append(["NORTH"])
                        else:
                            actions.append(["PASS"])
                else:
                    actions.append(["PASS"])

        else:
            # Fallback to greedy if scipy not installed
            assigned_tasks = set()
            for hand_pos in hands:
                best_task = None
                best_score = -math.inf
                best_path = []
                
                for task in tasks:
                    if id(task) in assigned_tasks:
                        continue
                        
                    target_pos = Position(task.target[0], task.target[1])
                    path = self.pathfinder.find_path(state, hand_pos, target_pos)
                    distance = len(path) - 1 if path else math.inf
                    score = task.priority - (distance * 4.0)
                    
                    if score > best_score:
                        best_score = score
                        best_task = task
                        best_path = path
                        
                if best_task and best_path:
                    assigned_tasks.add(id(best_task))
                    if len(best_path) <= 1:
                        if best_task.task_type.value == "HARVEST":
                            actions.append(["HARVEST", best_task.target[0], best_task.target[1]])
                        elif best_task.task_type.value == "WATER":
                            actions.append(["WATER", best_task.target[0], best_task.target[1]])
                        elif best_task.task_type.value == "PLANT":
                            actions.append(["PLANT", best_task.crop, best_task.target[0], best_task.target[1]])
                        elif best_task.task_type.value == "FERTILIZE":
                            actions.append(["FERTILIZE", best_task.target[0], best_task.target[1]])
                        elif best_task.task_type.value == "FEED":
                            actions.append(["FEED", best_task.target[0], best_task.target[1]])
                        elif best_task.task_type.value == "CARE":
                            actions.append(["CARE", best_task.target[0], best_task.target[1]])
                        elif best_task.task_type.value == "COLLECT_FERTILIZER":
                            actions.append(["COLLECT_FERTILIZER", best_task.target[0], best_task.target[1]])
                        elif best_task.task_type.value == "PLACE":
                            actions.append(["PLACE", best_task.crop, 1])
                        else:
                            actions.append(["PASS"])
                    else:
                        next_pos = best_path[1]
                        if next_pos.x > hand_pos.x:
                            actions.append(["EAST"])
                        elif next_pos.x < hand_pos.x:
                            actions.append(["WEST"])
                        elif next_pos.y > hand_pos.y:
                            actions.append(["SOUTH"])
                        elif next_pos.y < hand_pos.y:
                            actions.append(["NORTH"])
                        else:
                            actions.append(["PASS"])
                else:
                    actions.append(["PASS"])
                    
        return actions
