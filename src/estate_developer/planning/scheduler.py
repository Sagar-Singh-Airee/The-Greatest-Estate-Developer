"""
V1.5 Value-Aware Task Scheduler (Fully Optimised).

Changes from V1.4:
    - Watering now beats EVERYTHING (critical base = 3000 + 1000/unwatered day).
    - Movement cost tripled (15 per step) to discourage cross‑map treks.
    - Greedy fallback removed → farmer PASSes if A* cannot find a path.
    - Bulk pickup: grabs up to 5 units when visiting the shed.
    - Proximity bonus: adds a small discount for nearby tasks.
"""

from __future__ import annotations

from estate_developer.planning.tasks import (
    FarmTask,
    TaskType,
)

from estate_developer.execution.pathfinder import Pathfinder
from estate_developer.state.parser import Position


class TaskScheduler:
    """Select the most useful currently executable task."""

    SHED_TILES = (
        (4, 4),
        (5, 4),
        (4, 5),
        (5, 5),
    )

    ANIMALS = frozenset(("GOOSE", "COW", "SHEEP"))

    def __init__(self) -> None:
        self._pathfinder = Pathfinder()

    # --------------------------------------------------------
    # Safety weights (adjusted)
    # --------------------------------------------------------

    HARVEST_BASE = 1000

    WATER_CRITICAL_BASE = 3000          # was 1800
    WATER_NORMAL_BASE = 950

    PLACE_BASE = 700
    PLANT_BASE = 600
    BUY_SEED_BASE = 500
    PASS_BASE = 0

    # --------------------------------------------------------
    # Economic scaling
    # --------------------------------------------------------

    VALUE_WEIGHT = 2.0

    # Movement now expensive – farmer stays local
    MOVE_COST_PER_STEP = 15.0           # was 4.0
    LONG_ROUTE_PENALTY = 2.0            # was 1.0

    # Proximity bonus: adds a small nudge for nearby tasks
    PROXIMITY_BONUS_WEIGHT = 0.5

    # ========================================================
    # TASK SELECTION
    # ========================================================

    def choose(
        self,
        tasks: list[FarmTask],
        state,
    ) -> FarmTask:

        if not tasks:
            return FarmTask(
                task_type=TaskType.PASS,
                priority=self.PASS_BASE,
                reason="empty task list",
            )

        scored = []

        for task in tasks:
            score = self.score(task, state)
            scored.append((score, task))

        scored.sort(
            key=lambda item: (item[0], item[1].priority),
            reverse=True,
        )

        return scored[0][1]

    # ========================================================
    # SCORING (with proximity bonus)
    # ========================================================

    def score(
        self,
        task: FarmTask,
        state,
    ) -> float:
        """
        Compute task utility.

        Safety dominates.
        Economic value only breaks relatively safe choices.
        Proximity bonus favours nearby tasks.
        """

        x = state.me.farmer.x
        y = state.me.farmer.y

        score = float(task.priority)

        # ----------------------------------------------------
        # WATER – now beats harvest
        # ----------------------------------------------------

        if task.task_type == TaskType.WATER:
            tile = self._tile_at(
                state.me.tiles,
                *(task.target or (x, y)),
            )
            unwatered = 0
            if isinstance(tile, dict):
                unwatered = int(tile.get("consecutive_unwatered", 0))

            if unwatered >= 1:
                score = max(
                    score,
                    self.WATER_CRITICAL_BASE + 1000 * unwatered,
                )
            else:
                score = max(score, self.WATER_NORMAL_BASE)

        # ----------------------------------------------------
        # HARVEST VALUE
        # ----------------------------------------------------

        elif task.task_type == TaskType.HARVEST:
            tile = self._tile_at(
                state.me.tiles,
                *(task.target or (x, y)),
            )
            yield_units = 1
            if isinstance(tile, dict):
                yield_units = max(1, int(tile.get("yield_units", 1)))

            market_price = float(
                state.market.prices.get(task.crop or "WHEAT", 0)
            )
            economic_value = yield_units * market_price
            score += self.VALUE_WEIGHT * economic_value

        # ----------------------------------------------------
        # Other tasks – keep their base priority
        # ----------------------------------------------------

        # FEED, CARE, COLLECT_FERTILIZER, FERTILIZE, BUILD, DIG
        # Already have high priorities from generator.

        # PLACE / PLANT / BUY_SEED / etc. – no extra score

        # ----------------------------------------------------
        # MOVEMENT COST (now heavily penalised)
        # ----------------------------------------------------

        distance = self._task_distance(x, y, task)
        score -= distance * self.MOVE_COST_PER_STEP
        if distance > 5:
            score -= distance * self.LONG_ROUTE_PENALTY

        # ----------------------------------------------------
        # PROXIMITY BONUS – favours nearby tasks
        # ----------------------------------------------------

        # If distance is small, add a tiny bonus
        if distance <= 2:
            score += self.PROXIMITY_BONUS_WEIGHT * (3 - distance)

        return score

    # ========================================================
    # DISTANCE
    # ========================================================

    def _task_distance(
        self,
        x: int,
        y: int,
        task: FarmTask,
    ) -> int:

        if task.task_type == TaskType.PLACE:
            target = self._nearest_shed_tile(x, y)
            return abs(x - target[0]) + abs(y - target[1])

        if task.target is None:
            return 0

        return abs(x - task.target[0]) + abs(y - task.target[1])

    # ========================================================
    # FARMER ACTION (SAFE – no greedy fallback)
    # ========================================================

    def farmer_action(
        self,
        task: FarmTask,
        state,
    ) -> list[str]:
        x = state.me.farmer.x
        y = state.me.farmer.y

        # Market‑only tasks → farmer does physical work.
        if task.task_type in (
            TaskType.BUY_SEED,
            TaskType.BUY_ANIMAL,
            TaskType.HIRE,
            TaskType.BUY_LAND,
        ):
            return self._best_physical_action(state)

        if task.task_type == TaskType.PASS:
            return ["PASS"]

        # ---- Pickup logic – with BULK pickup ----
        if task.task_type == TaskType.FEED:
            supply_action = self._pickup_if_needed(state, "WHEAT", 1, bulk=5)
            if supply_action is not None:
                return supply_action

        if task.task_type == TaskType.FERTILIZE:
            supply_action = self._pickup_if_needed(state, "FERTILIZER", 1, bulk=5)
            if supply_action is not None:
                return supply_action

        # ---- PLACE (shed drop or animal placement) ----
        if task.task_type == TaskType.PLACE:
            is_animal_placement = task.crop in self.ANIMALS

            if is_animal_placement:
                supply_action = self._pickup_if_needed(state, task.crop or "", 1, bulk=1)
                if supply_action is not None:
                    return supply_action
                target = task.target
                if target is None:
                    return ["PASS"]
            else:
                target = self._nearest_shed_tile(x, y)

            # Move toward target using A* (NO greedy fallback)
            if (x, y) != target:
                path = self._pathfinder.find_path(
                    state,
                    Position(x, y),
                    Position(target[0], target[1]),
                )
                if path and len(path) > 1:
                    next_pos = path[1]
                    if next_pos.x > x:
                        return ["EAST"]
                    if next_pos.x < x:
                        return ["WEST"]
                    if next_pos.y > y:
                        return ["SOUTH"]
                    if next_pos.y < y:
                        return ["NORTH"]
                # No path → PASS (instead of greedy)
                return ["PASS"]

            return ["PLACE", task.crop, max(1, task.quantity)]

        # ---- Tile tasks ----
        if task.target is None:
            return ["PASS"]

        tx, ty = task.target

        if (x, y) != (tx, ty):
            path = self._pathfinder.find_path(
                state,
                Position(x, y),
                Position(tx, ty),
            )
            if path and len(path) > 1:
                next_pos = path[1]
                if next_pos.x > x:
                    return ["EAST"]
                if next_pos.x < x:
                    return ["WEST"]
                if next_pos.y > y:
                    return ["SOUTH"]
                if next_pos.y < y:
                    return ["NORTH"]
            # No path → PASS
            return ["PASS"]

        # At target – execute
        if task.task_type == TaskType.HARVEST:
            return ["HARVEST"]
        if task.task_type == TaskType.WATER:
            return ["WATER"]
        if task.task_type == TaskType.PLANT:
            return ["PLANT", task.crop]
        if task.task_type == TaskType.BUILD_COOP:
            return ["BUILD_COOP"]
        if task.task_type == TaskType.BUILD_PASTURE:
            return ["BUILD_PASTURE"]
        if task.task_type == TaskType.DIG:
            return ["DIG"]
        if task.task_type == TaskType.FERTILIZE:
            return ["FERTILIZE"]
        if task.task_type == TaskType.FEED:
            return ["FEED"]
        if task.task_type == TaskType.CARE:
            return ["CARE"]
        if task.task_type == TaskType.COLLECT_FERTILIZER:
            return ["COLLECT_FERTILIZER"]

        return ["PASS"]

    # ========================================================
    # PICKUP WITH BULK
    # ========================================================

    def _pickup_if_needed(
        self,
        state,
        item: str,
        quantity: int,
        bulk: int = 1,
    ) -> list[str] | None:
        """
        Return a movement/PICKUP action until the farmer carries the item.

        bulk: maximum units to pick up (e.g., 5 for WHEAT, 5 for FERTILIZER).
        """
        inventory = (
            state.private.inventories[0]
            if state.private.inventories
            else {}
        )
        held = int(inventory.get(item, 0))
        if held >= quantity:
            return None

        available = int(state.private.shed.get(item, 0))
        if available <= 0:
            return ["PASS"]

        x = state.me.farmer.x
        y = state.me.farmer.y
        target = self._nearest_shed_tile(x, y)

        if (x, y) != target:
            path = self._pathfinder.find_path(
                state,
                Position(x, y),
                Position(target[0], target[1]),
            )
            if path and len(path) > 1:
                next_pos = path[1]
                if next_pos.x > x:
                    return ["EAST"]
                if next_pos.x < x:
                    return ["WEST"]
                if next_pos.y > y:
                    return ["SOUTH"]
                if next_pos.y < y:
                    return ["NORTH"]
            return ["PASS"]

        # At shed – pick up enough to reduce future trips
        take = min(available, quantity - held + bulk - 1)  # grab up to `bulk` extra
        return ["PICKUP", item, take]

    # ========================================================
    # BEST PHYSICAL ACTION (safe PASS fallback)
    # ========================================================

    def _best_physical_action(self, state) -> list:
        """
        When the farmer has no specific task, find the nearest urgent physical work.
        """
        x = state.me.farmer.x
        y = state.me.farmer.y
        tiles = state.me.tiles

        candidates: list[tuple[float, str, int, int]] = []

        for ty_i, row in enumerate(tiles):
            for tx_i, tile in enumerate(row):
                if not isinstance(tile, dict):
                    continue

                kind = tile.get("kind")
                dist = abs(x - tx_i) + abs(y - ty_i)

                if kind == "PLANT":
                    unw = int(tile.get("consecutive_unwatered", 0))
                    watered = tile.get("watered_today", False)
                    yield_units = int(tile.get("yield_units", 0))

                    if not watered and unw >= 1:
                        candidates.append((10000 - dist, "WATER", tx_i, ty_i))
                    if yield_units > 0:
                        candidates.append((8000 - dist, "HARVEST", tx_i, ty_i))
                    if not watered and unw == 0:
                        candidates.append((6000 - dist, "WATER", tx_i, ty_i))

                elif kind == "WEED":
                    candidates.append((7500 - dist, "DIG", tx_i, ty_i))

                elif kind in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    if animal:
                        fed = tile.get("fed_today", False)
                        if not fed:
                            unf = int(tile.get("consecutive_unfed", 0))
                            sc = (9000 if unf >= 1 else 5000) - dist
                            candidates.append((sc, "FEED", tx_i, ty_i))
                        if int(tile.get("yield_units", 0)) > 0:
                            candidates.append((8500 - dist, "HARVEST", tx_i, ty_i))
                        if not tile.get("cared_today", False):
                            candidates.append((4000 - dist, "CARE", tx_i, ty_i))
                    if tile.get("fertilizer_available", False):
                        candidates.append((3500 - dist, "COLLECT_FERTILIZER", tx_i, ty_i))

        if not candidates:
            return ["PASS"]

        best = max(candidates, key=lambda c: c[0])
        action_str, tx, ty = best[1], best[2], best[3]

        if (x, y) == (tx, ty):
            return [action_str]

        # Navigate via A*, no greedy fallback
        path = self._pathfinder.find_path(
            state,
            Position(x, y),
            Position(tx, ty),
        )
        if path and len(path) > 1:
            next_pos = path[1]
            if next_pos.x > x:
                return ["EAST"]
            if next_pos.x < x:
                return ["WEST"]
            if next_pos.y > y:
                return ["SOUTH"]
            if next_pos.y < y:
                return ["NORTH"]

        # No path → PASS
        return ["PASS"]

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _tile_at(tiles, x: int, y: int):
        if y < 0 or y >= len(tiles):
            return None
        if x < 0 or x >= len(tiles[y]):
            return None
        return tiles[y][x]

    @classmethod
    def _nearest_shed_tile(cls, x: int, y: int) -> tuple[int, int]:
        return min(
            cls.SHED_TILES,
            key=lambda pos: abs(x - pos[0]) + abs(y - pos[1]),
        )