"""
V2.13 Dynamic Economic Task Generator.

Responsibilities:

    1. Discover work on the real farm.
    2. Protect existing crops.
    3. Detect free production slots.
    4. Ask the economic allocator which crop should occupy
       the next free slot.
    5. Generate BUY_SEED / PLANT tasks.
    6. Optimize fertilizer allocation based on marginal profit.
    7. Forecast labor demand and hire ahead of peaks.

V13: Fertilizer optimization, dynamic hiring, aggressive land acquisition.
"""

from __future__ import annotations

from estate_developer.economics.slot_allocator import (
    ProductionSlotAllocator,
)

from estate_developer.planning.tasks import (
    FarmTask,
    TaskType,
)

from estate_developer.planning.production_capacity import (
    discover_production_tiles,
    count_active_production,
)

from estate_developer.economics.price_forecaster import PriceForecaster


class TaskGenerator:

    # --------------------------------------------------------
    # Unlimited capacity for industrial farming
    # --------------------------------------------------------

    MAX_PRODUCTION_SLOTS = 30

    # Economic candidates currently validated.
    CANDIDATE_CROPS = (
        "WHEAT",
        "CARROT",
        "TOMATO",
        "STRAWBERRY",
        "MELON",
    )

    # Animals known by the allocator.
    ANIMAL_NAMES = ("GOOSE", "COW", "SHEEP")

    # Task priorities.
    FEED_CRITICAL_PRIORITY = 2000
    FEED_NORMAL_PRIORITY = 1500
    HARVEST_PRIORITY = 1100
    PLANT_PRIORITY = 950
    WATER_CRITICAL_PRIORITY = 1050
    FERTILIZE_PRIORITY = 870
    CARE_PRIORITY = 850
    WATER_NORMAL_PRIORITY = 800
    PLACE_ANIMAL_PRIORITY = 1250
    COLLECT_FERTILIZER_PRIORITY = 750
    PLACE_PRIORITY = 700
    BUY_SEED_PRIORITY = 990
    BUILD_PRIORITY = 980

    # Number of tiles permanently reserved for WHEAT production
    # when animals are on the farm.
    WHEAT_TILES_PER_4_ANIMALS = 1

    def __init__(self) -> None:
        self.allocator = ProductionSlotAllocator()

    # ========================================================
    # MAIN GENERATION
    # ========================================================

    def generate(
        self,
        state,
        *,
        max_active_wheat: int = 3,
    ) -> list[FarmTask]:
        """
        Generate all currently actionable tasks.
        """

        tasks: list[FarmTask] = []

        physical_free_tiles = discover_production_tiles(state.me.tiles)
        active_slots = count_active_production(state.me.tiles)

        current_day = int(state.day)

        # ---- Early-game script: rapid investment ----
        if current_day == 0:
            money = state.me.money

            # 1. Force buy animals
            if money >= 1300:
                tasks.append(
                    FarmTask(
                        task_type=TaskType.BUY_ANIMAL,
                        priority=1500,
                        crop="GOOSE",
                        quantity=1,
                        reason="early-game forced GOOSE"
                    )
                )
                tasks.append(
                    FarmTask(
                        task_type=TaskType.BUY_ANIMAL,
                        priority=1500,
                        crop="COW",
                        quantity=1,
                        reason="early-game forced COW"
                    )
                )
                if len(physical_free_tiles) >= 2:
                    tasks.append(
                        FarmTask(
                            task_type=TaskType.BUILD_COOP,
                            priority=1400,
                            target=physical_free_tiles[0],
                            crop="GOOSE",
                            reason="build coop for forced GOOSE"
                        )
                    )
                    tasks.append(
                        FarmTask(
                            task_type=TaskType.BUILD_PASTURE,
                            priority=1400,
                            target=physical_free_tiles[1],
                            crop="COW",
                            reason="build pasture for forced COW"
                        )
                    )

            # 2. Force hire one hand
            if len(state.me.hands) == 0 and money >= 10:
                tasks.append(
                    FarmTask(
                        task_type=TaskType.HIRE,
                        priority=1300,
                        quantity=1,
                        reason="early-game forced hire"
                    )
                )

            # 3. Buy and plant seeds to fill free tiles
            ranked = self.allocator.rank(state)
            best_crop = ranked[0].crop if ranked else "WHEAT"
            free_count = len(physical_free_tiles)
            seeds_to_buy = min(10, free_count)
            if seeds_to_buy > 0 and money >= seeds_to_buy * 10:
                tasks.append(
                    FarmTask(
                        task_type=TaskType.BUY_SEED,
                        priority=1200,
                        crop=best_crop,
                        quantity=seeds_to_buy,
                        reason=f"early fill {seeds_to_buy} tiles with {best_crop}"
                    )
                )
                for (tx, ty) in physical_free_tiles[:seeds_to_buy]:
                    tasks.append(
                        FarmTask(
                            task_type=TaskType.PLANT,
                            priority=1150,
                            target=(tx, ty),
                            crop=best_crop,
                            quantity=1,
                            reason="early planting"
                        )
                    )

        # ---- Animal census ----
        animal_count = sum(
            1
            for row in state.me.tiles
            for tile in row
            if isinstance(tile, dict)
            and tile.get("kind") in ("COOP", "PASTURE")
            and tile.get("animal")
        )
        wheat_reserve = max(0, (animal_count + 3) // 4) * self.WHEAT_TILES_PER_4_ANIMALS
        active_wheat = sum(
            1
            for row in state.me.tiles
            for tile in row
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "WHEAT"
        )

        # ---- Weeds ----
        for wy, wrow in enumerate(state.me.tiles):
            for wx, wtile in enumerate(wrow):
                if isinstance(wtile, dict) and wtile.get("kind") == "WEED":
                    tasks.append(
                        FarmTask(
                            task_type=TaskType.DIG,
                            priority=920,
                            target=(wx, wy),
                            reason="remove weed",
                        )
                    )

        # ---- Scan existing crops and animals ----
        for y, row in enumerate(state.me.tiles):
            for x, tile in enumerate(row):
                if not isinstance(tile, dict):
                    continue

                kind = tile.get("kind")

                if kind in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    if not animal:
                        continue

                    if not tile.get("fed_today", False):
                        unfed = int(tile.get("consecutive_unfed", 0))
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.FEED,
                                priority=(
                                    self.FEED_CRITICAL_PRIORITY
                                    if unfed >= 1
                                    else self.FEED_NORMAL_PRIORITY
                                ),
                                target=(x, y),
                                reason=f"feed {animal}"
                            )
                        )

                    if not tile.get("cared_today", False):
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.CARE,
                                priority=self.CARE_PRIORITY,
                                target=(x, y),
                                reason=f"care for {animal}"
                            )
                        )

                    if int(tile.get("yield_units", 0)) > 0:
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.HARVEST,
                                priority=self.HARVEST_PRIORITY,
                                target=(x, y),
                                crop=(
                                    "EGG" if animal == "GOOSE"
                                    else "MILK" if animal == "COW"
                                    else "WOOL"
                                ),
                                reason=f"harvest {animal} products",
                            )
                        )

                    if tile.get("fertilizer_available", False):
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.COLLECT_FERTILIZER,
                                priority=self.COLLECT_FERTILIZER_PRIORITY,
                                target=(x, y),
                                reason=f"collect fertilizer from {animal}",
                            )
                        )
                    continue

                if kind != "PLANT":
                    continue

                crop = tile.get("crop")

                if crop not in self.CANDIDATE_CROPS:
                    continue

                # Harvest
                if self._is_harvest_ready(tile, crop):
                    tasks.append(
                        FarmTask(
                            task_type=TaskType.HARVEST,
                            priority=self.HARVEST_PRIORITY,
                            target=(x, y),
                            crop=crop,
                            reason=f"harvest {crop}",
                        )
                    )
                    continue

                # Water
                if not tile.get("watered_today", False):
                    unwatered = int(tile.get("consecutive_unwatered", 0))
                    priority = (
                        self.WATER_CRITICAL_PRIORITY
                        if unwatered >= 1
                        else self.WATER_NORMAL_PRIORITY
                    )
                    tasks.append(
                        FarmTask(
                            task_type=TaskType.WATER,
                            priority=priority,
                            target=(x, y),
                            crop=crop,
                            reason=f"water {crop}",
                        )
                    )

        # ---- Place animals from shed onto empty structures ----
        ANIMAL_STRUCTURE_MAP = {
            "GOOSE": "COOP",
            "COW": "PASTURE",
            "SHEEP": "PASTURE",
        }

        for animal_name, needed_structure in ANIMAL_STRUCTURE_MAP.items():
            available_to_farmer = int(state.private.shed.get(animal_name, 0))
            if state.private.inventories:
                available_to_farmer += int(
                    state.private.inventories[0].get(animal_name, 0)
                )
            if available_to_farmer <= 0:
                continue

            for y2, row2 in enumerate(state.me.tiles):
                for x2, tile2 in enumerate(row2):
                    if not isinstance(tile2, dict):
                        continue
                    if (
                        tile2.get("kind") == needed_structure
                        and tile2.get("animal") is None
                    ):
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.PLACE,
                                priority=self.PLACE_ANIMAL_PRIORITY,
                                target=(x2, y2),
                                crop=animal_name,
                                quantity=1,
                                reason=f"place {animal_name} on {needed_structure}",
                            )
                        )
                        break
                else:
                    continue
                break

        # ---- FERTILIZER OPTIMIZER ----
        # Compute marginal profit for each crop tile and fertilize the highest ROI tiles.
        fert_available = (
            int(state.private.shed.get("FERTILIZER", 0))
            + sum(
                int(inv.get("FERTILIZER", 0))
                for inv in state.private.inventories
            )
        )

        if fert_available > 0:
            fertilizer_candidates = self._rank_fertilizer_targets(state)
            for (x2, y2, crop2, marginal_profit) in fertilizer_candidates:
                if fert_available <= 0:
                    break
                tasks.append(
                    FarmTask(
                        task_type=TaskType.FERTILIZE,
                        priority=self.FERTILIZE_PRIORITY + min(50, int(marginal_profit / 10)),
                        target=(x2, y2),
                        crop=crop2,
                        reason=f"fertilize {crop2} (profit +{marginal_profit:.0f})",
                    )
                )
                fert_available -= 1

        # ---- Economic allocation for free slots ----
        if active_slots < self.MAX_PRODUCTION_SLOTS:
            candidate = self._best_feasible_crop(state)

            if animal_count > 0 and active_wheat < wheat_reserve:
                # Override with WHEAT
                from estate_developer.economics.slot_allocator import SlotCandidate as _SC
                candidate = _SC(
                    crop="WHEAT",
                    batch_size=4,
                    market_inventory=int(state.market.inventory.get("WHEAT", self.allocator.MAX_PRODUCTION_SLOTS)),
                    starting_price=float(state.market.prices.get("WHEAT", 25)),
                    ending_price=float(state.market.prices.get("WHEAT", 25)),
                    realized_revenue=4 * float(state.market.prices.get("WHEAT", 25)),
                    seed_cost=10.0,
                    contribution=4 * float(state.market.prices.get("WHEAT", 25)) - 10.0,
                    production_days=4,
                    remaining_days_after_harvest=0,
                    contribution_per_tile_day=(4 * float(state.market.prices.get("WHEAT", 25)) - 10.0) / 4.0,
                    season_feasible=True,
                )

            if candidate is not None:
                chosen = candidate.crop

                if chosen in self.ANIMAL_NAMES:
                    from estate_developer.economics.slot_allocator import (
                        ProductionSlotAllocator,
                    )
                    animal_profile = (
                        ProductionSlotAllocator.ANIMAL_PROFILES[chosen]
                    )
                    setup_action = animal_profile["setup_action"]

                    target = self._find_empty_production_tile(
                        state.me.tiles,
                        prefer_near_shed=True,
                    )

                    if target is not None:
                        task_type = (
                            TaskType.BUILD_COOP
                            if setup_action == "BUILD_COOP"
                            else TaskType.BUILD_PASTURE
                        )
                        tasks.append(
                            FarmTask(
                                task_type=task_type,
                                priority=self.BUILD_PRIORITY,
                                target=target,
                                crop=chosen,
                                reason=f"allocator: build {setup_action} for {chosen}",
                            )
                        )

                else:
                    crop = chosen
                    seed_count = int(state.private.seeds.get(crop, 0))

                    if seed_count > 0:
                        all_free = sorted(
                            discover_production_tiles(state.me.tiles),
                            key=lambda c: -(c[0] + c[1])
                        )
                        remaining_seeds = seed_count
                        for t_target in all_free:
                            if remaining_seeds <= 0:
                                break
                            tasks.append(
                                FarmTask(
                                    task_type=TaskType.PLANT,
                                    priority=self.PLANT_PRIORITY,
                                    target=t_target,
                                    crop=crop,
                                    quantity=1,
                                    reason=f"economic allocator: {crop}",
                                )
                            )
                            remaining_seeds -= 1
                    else:
                        profile = self._profile(crop)
                        free_tiles = len(self._find_empty_production_tiles(state.me.tiles))
                        unlock_count = len(state.me.unlocked_quadrants)
                        next_land_cost = (1000, 2000, 4000)[
                            min(max(0, unlock_count - 1), 2)
                        ]
                        reserve = 250
                        if free_tiles <= 6 and unlock_count < 4:
                            reserve += next_land_cost
                        investable_cash = max(0, int(state.me.money - reserve))
                        affordable = investable_cash // max(1, profile.seed_cost)
                        portfolio = self.allocator.crop_portfolio(
                            state, min(free_tiles, 8)
                        )
                        desired = max(1, portfolio.count(crop))
                        tranche = min(3, free_tiles, desired, affordable)

                        if tranche > 0:
                            tasks.append(
                                FarmTask(
                                    task_type=TaskType.BUY_SEED,
                                    priority=self.BUY_SEED_PRIORITY,
                                    crop=crop,
                                    quantity=tranche,
                                    reason=f"diversified capital: {tranche}x {crop}",
                                )
                            )

        # ---- DYNAMIC HIRING ----
        # Predict labor demand for the next 5 days and hire ahead of peaks.
        labor_demand = self._forecast_labor_demand(state, days=5)
        current_hands = len(state.me.hands)
        projected_peak = max(labor_demand.values()) if labor_demand else 0

        # We want enough hands to handle the peak day's workload, plus some buffer.
        target_hands = max(
            current_hands,
            projected_peak + 1,  # +1 buffer
        )

        hires_needed = target_hands - current_hands
        hires_today = state.me.hires_today

        # Fibonacci hire costs
        _FIB = (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
        total_hire_cost = 0
        temp_hires = hires_today
        for _ in range(hires_needed):
            fib_val = _FIB[min(temp_hires, len(_FIB) - 1)]
            total_hire_cost += 10 * fib_val
            temp_hires += 1

        cash_buffer = 100
        if hires_needed > 0 and state.me.money >= total_hire_cost + cash_buffer:
            tasks.append(
                FarmTask(
                    task_type=TaskType.HIRE,
                    priority=self.BUY_SEED_PRIORITY + 1,
                    quantity=hires_needed,
                    reason=f"hire {hires_needed} hands for projected peak workload",
                )
            )

        # ---- AGGRESSIVE LAND BUYING ----
        # Buy land as soon as we can afford it, even if we still have free tiles.
        physical_free = len(self._find_empty_production_tiles(state.me.tiles))
        _LAND_PRICES = (1000, 2000, 4000)
        _unlocked_count = len(getattr(state.me, "unlocked_quadrants", []) or [])
        _next_land_cost = _LAND_PRICES[min(_unlocked_count - 1, len(_LAND_PRICES) - 1)] if _unlocked_count >= 1 else 1000

        # Always buy land if we have money and haven't maxed out yet
        if _unlocked_count < 4 and state.me.money >= _next_land_cost + 200:
            tasks.append(
                FarmTask(
                    task_type=TaskType.BUY_LAND,
                    priority=self.BUY_SEED_PRIORITY + 3,
                    quantity=1,
                    reason=f"aggressive land buy (${_next_land_cost})",
                )
            )

        # ---- Fallback ----
        if not tasks:
            tasks.append(
                FarmTask(
                    task_type=TaskType.PASS,
                    priority=0,
                    reason="no executable work",
                )
            )

        tasks.sort(
            key=lambda task: task.priority,
            reverse=True,
        )

        return tasks

    # ========================================================
    # FERTILIZER OPTIMIZER
    # ========================================================

    def _rank_fertilizer_targets(self, state) -> list[tuple[int, int, str, float]]:
        """
        Returns list of (x, y, crop, marginal_profit) sorted by highest marginal profit.
        Marginal profit = (yield_increase * price) - opportunity_cost.
        """
        candidates = []
        forecaster = PriceForecaster(state)

        for y, row in enumerate(state.me.tiles):
            for x, tile in enumerate(row):
                if not isinstance(tile, dict):
                    continue
                if tile.get("kind") != "PLANT":
                    continue

                crop = tile.get("crop", "")
                if crop not in ("MELON", "STRAWBERRY", "WHEAT", "CARROT", "TOMATO"):
                    continue

                # Check if already fertilized
                fert_until = int(tile.get("fertilized_until_day", -1))
                if fert_until >= int(state.day):
                    continue

                # Get crop profile
                from estate_developer.economics.crops import CROP_PROFILES
                profile = CROP_PROFILES.get(crop)
                if not profile:
                    continue

                # Yield increase from fertilizer
                if profile.yield_type == "ONE_TIME":
                    # Fertilizer can increase yield from max_yield_unfertilized to max_yield_fertilized
                    base_yield = float(profile.max_yield_unfertilized)
                    fert_yield = float(profile.max_yield_fertilized)
                    yield_increase = max(0, fert_yield - base_yield)
                else:
                    # Ongoing crops: fertilizer doubles each yield tick (but same total max)
                    # We'll approximate: +1 per remaining yield tick
                    current_age = int(state.day) - int(tile.get("planted_day", state.day))
                    first_yield = int(profile.first_yield_day)
                    interval = int(profile.yield_interval)
                    remaining_ticks = 0
                    if current_age < first_yield:
                        remaining_ticks = (first_yield - current_age) // interval + 1
                    else:
                        remaining_ticks = (profile.max_yield_unfertilized - int(tile.get("yield_units", 0)))
                    yield_increase = min(remaining_ticks, 4) * 0.5  # approx +0.5 per tick

                # Price at harvest (estimate 2-3 days from now)
                harvest_day = int(state.day) + profile.max_yield_day - int(tile.get("planted_day", state.day))
                # Simple price estimate
                price = forecaster.forecast_price(crop, steps_ahead=48)  # 2 days
                if price == 0:
                    price = float(state.market.prices.get(crop, profile.base_price))

                marginal_profit = yield_increase * price

                # Opportunity cost: fertilizer could be used elsewhere
                marginal_profit -= 25  # small discount for opportunity cost

                if marginal_profit > 20:  # Only consider if worth it
                    candidates.append((x, y, crop, marginal_profit))

        # Sort by marginal profit descending
        candidates.sort(key=lambda c: c[3], reverse=True)
        return candidates

    # ========================================================
    # LABOR DEMAND FORECASTER
    # ========================================================

    def _forecast_labor_demand(self, state, days: int = 5) -> dict[int, int]:
        """
        Predicts the number of farmer/hand actions needed on each future day.
        Returns dict day_offset -> expected_actions.
        """
        demand = {d: 0 for d in range(1, days + 1)}
        current_day = int(state.day)

        # Count existing crops and their future needs
        for y, row in enumerate(state.me.tiles):
            for x, tile in enumerate(row):
                if not isinstance(tile, dict):
                    continue

                kind = tile.get("kind")

                if kind == "PLANT":
                    crop = tile.get("crop", "")
                    if crop not in self.CANDIDATE_CROPS:
                        continue

                    # Water: every day until harvest
                    from estate_developer.economics.crops import CROP_PROFILES
                    profile = CROP_PROFILES.get(crop)
                    if not profile:
                        continue

                    planted_day = int(tile.get("planted_day", current_day))
                    max_yield_day = int(profile.max_yield_day)
                    harvest_day = planted_day + max_yield_day

                    for d in range(1, days + 1):
                        day_offset = current_day + d
                        if day_offset < harvest_day:
                            # Needs watering (unless already watered today)
                            if not tile.get("watered_today", False):
                                demand[d] += 1
                        elif day_offset == harvest_day:
                            # Needs harvesting
                            demand[d] += 1

                elif kind in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    if not animal:
                        continue

                    # Animals need daily care + feed
                    for d in range(1, days + 1):
                        if not tile.get("fed_today", False):
                            demand[d] += 1  # feed
                        if not tile.get("cared_today", False):
                            demand[d] += 1  # care
                        if int(tile.get("yield_units", 0)) > 0:
                            demand[d] += 1  # harvest

        # Add planned planting from economic allocation
        free_tiles = len(discover_production_tiles(state.me.tiles))
        if free_tiles > 0 and state.me.money > 100:
            # We'll likely plant something in the next couple days
            for d in range(1, min(3, days) + 1):
                demand[d] += min(2, free_tiles)  # conservative estimate

        return demand

    # ========================================================
    # ECONOMIC SELECTION
    # ========================================================

    def _best_feasible_crop(self, state):
        ranked = self.allocator.rank(state)
        valid_names = set(self.CANDIDATE_CROPS) | set(self.ANIMAL_NAMES)

        for candidate in ranked:
            if candidate.crop in self.CANDIDATE_CROPS and state.private.seeds.get(candidate.crop, 0) > 0:
                return candidate

        animal_count = sum(
            1
            for row in state.me.tiles
            for tile in row
            if isinstance(tile, dict)
            and tile.get("kind") in ("COOP", "PASTURE")
            and tile.get("animal")
        )
        usable_tiles = sum(
            1
            for row in state.me.tiles
            for tile in row
            if tile != "LOCKED"
        )
        herd_cap = max(1, usable_tiles // 6)

        for candidate in ranked:
            if candidate.crop not in valid_names:
                continue
            if candidate.crop in self.ANIMAL_NAMES and animal_count >= herd_cap:
                continue
            return candidate

        return None

    # ========================================================
    # CROP PROFILE
    # ========================================================

    @staticmethod
    def _profile(crop: str):
        from estate_developer.economics.crops import (
            CROP_PROFILES,
        )
        return CROP_PROFILES[crop]

    # ========================================================
    # HELPERS
    # ========================================================

    def _find_empty_production_tiles(self, tiles) -> list[tuple[int, int]]:
        from estate_developer.planning.production_capacity import discover_production_tiles
        return discover_production_tiles(tiles)

    # ========================================================
    # HARVEST LOGIC
    # ========================================================

    @classmethod
    def _is_harvest_ready(cls, tile: dict, crop: str) -> bool:
        from estate_developer.economics.crops import CROP_PROFILES
        profile = CROP_PROFILES[crop]
        yield_units = int(tile.get("yield_units", 0))
        return yield_units >= profile.max_yield_unfertilized

    # ========================================================
    # INVENTORY
    # ========================================================

    def _farmer_carrying_any_candidate(self, state) -> bool:
        inventory = state.private.inventories[0] if state.private.inventories else {}
        return any(int(inventory.get(crop, 0)) > 0 for crop in self.CANDIDATE_CROPS)

    def _shed_contains_candidate(self, state) -> bool:
        return any(int(state.private.shed.get(crop, 0)) > 0 for crop in self.CANDIDATE_CROPS)

    # ========================================================
    # BOARD HELPERS
    # ========================================================

    @staticmethod
    def _tile_at(tiles, x: int, y: int):
        if y < 0 or y >= len(tiles):
            return None
        if x < 0 or x >= len(tiles[y]):
            return None
        return tiles[y][x]

    def _find_empty_production_tile(self, tiles, prefer_near_shed: bool = False):
        production_tiles = discover_production_tiles(tiles)
        if not production_tiles:
            return None
        if prefer_near_shed:
            sorted_tiles = sorted(production_tiles, key=lambda c: c[0] + c[1])
        else:
            sorted_tiles = sorted(production_tiles, key=lambda c: -(c[0] + c[1]))
        return sorted_tiles[0]