
"""
V2.12 Dynamic Economic Task Generator.

Responsibilities:

    1. Discover work on the real farm.
    2. Protect existing crops.
    3. Detect free production slots.
    4. Ask the economic allocator which crop should occupy
       the next free slot.
    5. Generate BUY_SEED / PLANT tasks.

Important rule:

    Existing healthy crops are NEVER replaced.

Only empty production slots are economically allocated.
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


class TaskGenerator:

    # --------------------------------------------------------
    # Unleash capacity limits for industrial farming
    # --------------------------------------------------------

    MAX_PRODUCTION_SLOTS = 100

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
    HARVEST_PRIORITY = 1000
    PLANT_PRIORITY = 950
    WATER_CRITICAL_PRIORITY = 900
    FERTILIZE_PRIORITY = 870
    CARE_PRIORITY = 850
    WATER_NORMAL_PRIORITY = 800
    PLACE_ANIMAL_PRIORITY = 780
    COLLECT_FERTILIZER_PRIORITY = 750
    PLACE_PRIORITY = 700
    BUY_SEED_PRIORITY = 990
    BUILD_PRIORITY = 980

    # Number of tiles permanently reserved for WHEAT production
    # when animals are on the farm. One tile of wheat yields ~4
    # units per 4-day cycle = 1 unit/day, easily feeding 1 animal.
    # Reserve 1 tile per 4 animals as a hard minimum.
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

        `max_active_wheat` is retained for compatibility with
        the V1.4 agent interface but is no longer used as a
        crop-specific limit.

        The actual constraint is:
            MAX_PRODUCTION_SLOTS = 5
        """

        tasks: list[FarmTask] = []

        # Physical production capacity is discovered
        # dynamically from the live farm.
        production_tiles = (
            discover_production_tiles(
                state.me.tiles
            )
        )

        # The economic utilization ceiling.
        active_slots = count_active_production(
            state.me.tiles
        )

        # ---- Animal census ----
        # Count animals currently on farm to calculate wheat reserve.
        animal_count = sum(
            1
            for row in state.me.tiles
            for tile in row
            if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE") and "animal" in tile
        )
        # How many wheat tiles we must always keep growing.
        wheat_reserve = max(0, (animal_count + 3) // 4) * self.WHEAT_TILES_PER_4_ANIMALS
        # Count current active wheat tiles.
        active_wheat = sum(
            1
            for row in state.me.tiles
            for tile in row
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "WHEAT"
        )

        # ----------------------------------------------------
        # 0. Weed removal — clear before crops block planting.
        # Weeds spread and have 0.5% spawn chance per empty tile
        # per turn. Must be cleared aggressively.
        # ----------------------------------------------------

        for wy, wrow in enumerate(state.me.tiles):
            for wx, wtile in enumerate(wrow):
                if isinstance(wtile, dict) and wtile.get("kind") == "WEED":
                    tasks.append(
                        FarmTask(
                            task_type=TaskType.DIG,
                            priority=920,  # above WATER_CRITICAL(900), below HARVEST
                            target=(wx, wy),
                            reason="remove weed to restore production tile",
                        )
                    )

        # ----------------------------------------------------
        # 1. Scan all active production crops.
        # ----------------------------------------------------

        for y, row in enumerate(
            state.me.tiles
        ):

            for x, tile in enumerate(
                row
            ):

                if not isinstance(
                    tile,
                    dict,
                ):
                    continue

                if tile.get(
                    "kind"
                ) != "PLANT":
                    continue

                crop = tile.get(
                    "crop"
                )

                if crop not in self.CANDIDATE_CROPS:
                    continue

                # ------------------------------------------------
                # HARVEST
                # ------------------------------------------------

                if self._is_harvest_ready(
                    tile,
                    crop,
                ):

                    tasks.append(
                        FarmTask(
                            task_type=TaskType.HARVEST,
                            priority=self.HARVEST_PRIORITY,
                            target=(x, y),
                            crop=crop,
                            reason=(
                                f"{crop.lower()} reached "
                                "peak batch yield"
                            ),
                        )
                    )

                    # Harvest outranks routine watering.
                    continue

                # ------------------------------------------------
                # WATER
                # ------------------------------------------------

                if not tile.get(
                    "watered_today",
                    False,
                ):

                    unwatered = int(
                        tile.get(
                            "consecutive_unwatered",
                            0,
                        )
                    )

                    if unwatered >= 1:

                        priority = (
                            self.WATER_CRITICAL_PRIORITY
                        )

                        reason = (
                            f"{crop.lower()} is approaching "
                            "watering failure"
                        )

                    else:

                        priority = (
                            self.WATER_NORMAL_PRIORITY
                        )

                        reason = (
                            f"{crop.lower()} requires "
                            "daily watering"
                        )

                    tasks.append(
                        FarmTask(
                            task_type=TaskType.WATER,
                            priority=priority,
                            target=(x, y),
                            crop=crop,
                            reason=reason,
                        )
                    )
                    
                # ------------------------------------------------
                # ANIMALS (COOP / PASTURE)
                # ------------------------------------------------
                elif tile.get("kind") in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    if not animal:
                        continue
                        
                    # 1. FEED
                    if not tile.get("fed_today", False):
                        unfed = int(tile.get("consecutive_unfed", 0))
                        if unfed >= 1:
                            priority = self.FEED_CRITICAL_PRIORITY
                            reason = f"{animal} is starving and will escape"
                        else:
                            priority = self.FEED_NORMAL_PRIORITY
                            reason = f"{animal} needs daily feed"
                            
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.FEED,
                                priority=priority,
                                target=(x, y),
                                reason=reason,
                            )
                        )
                        
                    # 2. CARE
                    if not tile.get("cared_today", False):
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.CARE,
                                priority=self.CARE_PRIORITY,
                                target=(x, y),
                                reason=f"care for {animal} to bank yield",
                            )
                        )
                        
                    # 3. HARVEST ANIMAL PRODUCTS
                    yield_units = int(tile.get("yield_units", 0))
                    if yield_units > 0:
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.HARVEST,
                                priority=self.HARVEST_PRIORITY,
                                target=(x, y),
                                reason=f"harvest products from {animal}",
                            )
                        )
                        
                    # 4. COLLECT FERTILIZER
                    if tile.get("fertilizer_available", False):
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.COLLECT_FERTILIZER,
                                priority=self.COLLECT_FERTILIZER_PRIORITY,
                                target=(x, y),
                                reason=f"collect fertilizer from {animal}",
                            )
                        )

        # ----------------------------------------------------
        # 1b. PLACE animals from shed onto empty structures.
        # ----------------------------------------------------

        ANIMAL_STRUCTURE_MAP = {
            "GOOSE": "COOP",
            "COW": "PASTURE",
            "SHEEP": "PASTURE",
        }

        for animal_name, needed_structure in ANIMAL_STRUCTURE_MAP.items():
            in_shed = int(
                state.private.shed.get(animal_name, 0)
            )
            if in_shed <= 0:
                continue

            # Find an empty structure to place the animal on
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
                                reason=(
                                    f"place {animal_name} from shed "
                                    f"onto {needed_structure}"
                                ),
                            )
                        )
                        break  # one animal per structure scan
                else:
                    continue
                break

        # ----------------------------------------------------
        # 1c. FERTILIZE high-value crops.
        # ----------------------------------------------------

        FERTILIZE_CROPS = ("MELON", "STRAWBERRY", "WHEAT", "CARROT")

        fert_available = (
            int(state.private.shed.get("FERTILIZER", 0))
            + sum(
                int(inv.get("FERTILIZER", 0))
                for inv in state.private.inventories
            )
        )

        if fert_available > 0:
            for y2, row2 in enumerate(state.me.tiles):
                for x2, tile2 in enumerate(row2):
                    if not isinstance(tile2, dict):
                        continue
                    if tile2.get("kind") != "PLANT":
                        continue
                    crop2 = tile2.get("crop", "")
                    if crop2 not in FERTILIZE_CROPS:
                        continue

                    fert_until = int(
                        tile2.get("fertilized_until_day", -1)
                    )
                    if fert_until >= int(state.day):
                        continue  # already fertilized

                    tasks.append(
                        FarmTask(
                            task_type=TaskType.FERTILIZE,
                            priority=self.FERTILIZE_PRIORITY,
                            target=(x2, y2),
                            crop=crop2,
                            reason=(
                                f"fertilize {crop2} to double "
                                "yield bonus"
                            ),
                        )
                    )
                    fert_available -= 1
                    if fert_available <= 0:
                        break
                if fert_available <= 0:
                    break

        # ----------------------------------------------------
        # 2. Harvested inventory → shed.
        # ----------------------------------------------------

        inventory = (
            state.private.inventories[0]
            if state.private.inventories
            else {}
        )

        # Include animal products in the shed-transfer scan
        ALL_SELLABLE = list(self.CANDIDATE_CROPS) + [
            "EGG", "MILK", "WOOL", "FERTILIZER",
        ]

        for item in ALL_SELLABLE:

            quantity = int(
                inventory.get(
                    item,
                    0,
                )
            )

            if quantity > 0:

                tasks.append(
                    FarmTask(
                        task_type=TaskType.PLACE,
                        priority=self.PLACE_PRIORITY,
                        crop=item,
                        quantity=quantity,
                        reason=(
                            f"move harvested "
                            f"{item.lower()} to shed"
                        ),
                    )
                )

                break

        # ----------------------------------------------------
        # 3. Economic allocation of a FREE slot.
        # ----------------------------------------------------

        if active_slots < self.MAX_PRODUCTION_SLOTS:

            candidate = self._best_feasible_crop(
                state
            )

            # ---- Feed safety override ----
            # If animals need wheat and we're below the reserve,
            # force WHEAT regardless of what the allocator picks.
            if (
                animal_count > 0
                and active_wheat < wheat_reserve
                and candidate is not None
                and candidate.crop != "WHEAT"
            ):
                # Override with WHEAT to prevent starvation.
                from estate_developer.economics.crops import CROP_PROFILES as _CP
                # Manufacture a pseudo-candidate pointing at WHEAT.
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

                # ----------------------------------------
                # CASE A: The allocator chose an ANIMAL.
                # ----------------------------------------
                if chosen in self.ANIMAL_NAMES:

                    from estate_developer.economics.slot_allocator import (
                        ProductionSlotAllocator,
                    )
                    animal_profile = (
                        ProductionSlotAllocator.ANIMAL_PROFILES[chosen]
                    )
                    setup_action = animal_profile["setup_action"]

                    # Zone: animals go near the shed for minimal daily walking
                    target = self._find_empty_production_tile(
                        state.me.tiles,
                        prefer_near_shed=True,
                    )

                    if target is not None:

                        # 1. Build the structure first.
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
                                reason=(
                                    f"allocator: build {setup_action} "
                                    f"for {chosen}"
                                ),
                            )
                        )

                    # 2. Queue a properly-typed BUY_ANIMAL market order.
                    if state.me.money >= animal_profile["cost"]:
                        tasks.append(
                            FarmTask(
                                task_type=TaskType.BUY_ANIMAL,
                                priority=self.BUY_SEED_PRIORITY,
                                crop=chosen,
                                quantity=1,
                                reason=(
                                    f"allocator: buy {chosen} "
                                    "for investment"
                                ),
                            )
                        )

                # ----------------------------------------
                # CASE B: The allocator chose a CROP.
                # ----------------------------------------
                else:

                    crop = chosen

                    seed_count = int(
                        state.private.seeds.get(
                            crop,
                            0,
                        )
                    )

                    # Plant immediately if the correct seed exists —
                    # generate PLANT tasks for ALL free tiles so hands
                    # can work in parallel (one task per tile, capped by seeds).
                    if seed_count > 0:
                        # Get ALL free production tiles sorted far-from-shed
                        _all_free = sorted(
                            discover_production_tiles(state.me.tiles),
                            key=lambda c: -(c[0] + c[1])  # far tiles first
                        )
                        _remaining_seeds = seed_count
                        for _t_target in _all_free:
                            if _remaining_seeds <= 0:
                                break
                            tasks.append(
                                FarmTask(
                                    task_type=TaskType.PLANT,
                                    priority=self.PLANT_PRIORITY,
                                    target=_t_target,
                                    crop=crop,
                                    quantity=1,
                                    reason=(
                                        "economic allocator selected "
                                        f"{crop}"
                                    ),
                                )
                            )
                            _remaining_seeds -= 1

                    # Otherwise bulk-buy enough seeds to fill ALL free slots at once.
                    # This ensures we invest money immediately instead of buying 1 per turn.
                    else:

                        if not self._shed_contains_candidate(
                            state
                        ):

                            profile = self._profile(crop)

                            if (
                                state.me.money
                                >= profile.seed_cost
                            ):
                                # Count how many free production tiles we have
                                _free_tiles = len(self._find_empty_production_tiles(state.me.tiles))
                                # Buy enough seeds to fill them all (capped by budget and market orders limit)
                                _can_afford = max(1, int(state.me.money * 0.6 / max(1, profile.seed_cost)))
                                _bulk_qty = max(1, min(_free_tiles, _can_afford, 10))

                                tasks.append(
                                    FarmTask(
                                        task_type=TaskType.BUY_SEED,
                                        priority=self.BUY_SEED_PRIORITY,
                                        crop=crop,
                                        quantity=_bulk_qty,
                                        reason=(
                                            f"economic allocator bulk-buying "
                                            f"{_bulk_qty}x {crop}"
                                        ),
                                    )
                                )

        # ----------------------------------------------------
        # 4. Fallback
        # ----------------------------------------------------

        if not tasks:

            tasks.append(
                FarmTask(
                    task_type=TaskType.PASS,
                    priority=0,
                    reason="no executable work",
                )
            )

        # ----------------------------------------------------
        # 5. Dynamic Expansion (Hire / Buy Land)
        # ----------------------------------------------------
        
        # If we have task backlog and minimal cash buffer, hire!
        # Real hire cost uses Fibonacci: fib(n) where n = hires_today.
        # fib: 1,1,2,3,5,8,13,21... multiply by farmHandCostMult=10 → 10,10,20,30,50,80...
        hires_today = state.me.hires_today
        _FIB = (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
        _fib_val = _FIB[min(hires_today, len(_FIB) - 1)]
        hire_cost = 10 * _fib_val  # farmHandCostMult=10 from reference rules
        
        # Count high priority manual tasks (excluding PASS and market orders)
        manual_tasks = sum(1 for t in tasks if t.task_type.value not in ("PASS", "BUY_SEED") and t.priority >= self.WATER_NORMAL_PRIORITY)
        hands_count = len(state.me.hands)
        
        # Aggressive industrial hiring: hire whenever the backlog per hand
        # exceeds 4 tasks. A 10-tile farm with 1 hand is massively bottlenecked.
        # Backlog per hand = manual_tasks / max(1, hands_count)
        hands_count = len(state.me.hands)
        tasks_per_hand = manual_tasks / max(1, hands_count + 1)  # +1 for farmer
        if tasks_per_hand > 4 and state.me.money >= hire_cost + 150:
            tasks.append(
                FarmTask(
                    task_type=TaskType.HIRE,
                    priority=self.BUY_SEED_PRIORITY + 1,
                    quantity=1,
                    reason="hire additional worker to aggressively clear task backlog"
                )
            )
            
        # Proactive land expansion: buy before completely running out.
        # Trigger when fewer than 5 free tiles remain — gives the agent
        # one full planning cycle to acquire land before being capacity-blocked.
        # Land costs: NE=$1000, SW=$2000, SE=$4000.
        physical_free = len(self._find_empty_production_tiles(state.me.tiles))
        _LAND_PRICES = (1000, 2000, 4000)  # NE, SW, SE in unlock order
        _unlocked_count = len(getattr(state.me, "unlocked_quadrants", []) or [])
        _next_land_cost = _LAND_PRICES[min(_unlocked_count - 1, len(_LAND_PRICES) - 1)] if _unlocked_count >= 1 else 1000
        _land_budget = _next_land_cost + 500
        # Buy when < 5 free tiles remain (proactive) OR when completely out
        if physical_free < 5 and active_slots < self.MAX_PRODUCTION_SLOTS and state.me.money >= _land_budget:
            tasks.append(
                FarmTask(
                    task_type=TaskType.BUY_LAND,
                    priority=self.BUY_SEED_PRIORITY + 2,
                    quantity=1,
                    reason=f"buy land (${_next_land_cost}) for industrial capacity expansion"
                )
            )

        tasks.sort(
            key=lambda task: task.priority,
            reverse=True,
        )

        return tasks

    # ========================================================
    # ECONOMIC SELECTION
    # ========================================================

    def _best_feasible_crop(
        self,
        state,
    ):
        """Return best currently feasible economic crop (or animal)."""

        ranked = self.allocator.rank(
            state
        )

        valid_names = set(self.CANDIDATE_CROPS) | set(self.ANIMAL_NAMES)

        for candidate in ranked:
            if candidate.crop in valid_names:
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
        # Returns a list of all free tile coordinates
        return discover_production_tiles(tiles)

    # ========================================================
    # HARVEST LOGIC
    # ========================================================

    @classmethod
    def _is_harvest_ready(
        cls,
        tile: dict,
        crop: str,
    ) -> bool:

        from estate_developer.economics.crops import (
            CROP_PROFILES,
        )

        profile = CROP_PROFILES[crop]

        yield_units = int(
            tile.get(
                "yield_units",
                0,
            )
        )

        # For current V2 candidates this represents peak
        # one-time batch yield.
        return (
            yield_units
            >= profile.max_yield_unfertilized
        )

    # ========================================================
    # INVENTORY
    # ========================================================

    def _farmer_carrying_any_candidate(
        self,
        state,
    ) -> bool:

        inventory = (
            state.private.inventories[0]
            if state.private.inventories
            else {}
        )

        return any(
            int(
                inventory.get(
                    crop,
                    0,
                )
            ) > 0
            for crop in self.CANDIDATE_CROPS
        )

    def _shed_contains_candidate(
        self,
        state,
    ) -> bool:

        return any(
            int(
                state.private.shed.get(
                    crop,
                    0,
                )
            ) > 0
            for crop in self.CANDIDATE_CROPS
        )

    # ========================================================
    # BOARD HELPERS
    # ========================================================

    @staticmethod
    def _tile_at(
        tiles,
        x: int,
        y: int,
    ):

        if y < 0 or y >= len(tiles):
            return None

        if x < 0 or x >= len(tiles[y]):
            return None

        return tiles[y][x]

    def _find_empty_production_tile(
        self,
        tiles,
        prefer_near_shed: bool = False,
    ):
        """
        Return the best empty production tile for the given use case.

        prefer_near_shed=True  → animals/structures (daily maintenance):
            Clusters near the shed origin (0,0) to minimise daily
            CARE/FEED/COLLECT walking distances.

        prefer_near_shed=False → crops (planted once, watered daily but
            otherwise low-maintenance): Picks tiles away from origin so
            that crops and animals don't compete for the same prime real
            estate.
        """
        production_tiles = discover_production_tiles(tiles)

        if not production_tiles:
            return None

        if prefer_near_shed:
            # Sort by Manhattan distance to shed (corner at 0,0)
            sorted_tiles = sorted(production_tiles, key=lambda c: c[0] + c[1])
        else:
            # Push crops to the far end of the board
            sorted_tiles = sorted(production_tiles, key=lambda c: -(c[0] + c[1]))

        return sorted_tiles[0]
