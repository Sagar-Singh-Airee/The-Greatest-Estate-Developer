import unittest

from estate_developer.economics.market import simulate_sale
from estate_developer.economics.market_manager import MarketManager
from estate_developer.economics.slot_allocator import ProductionSlotAllocator
from estate_developer.planning.generator import TaskGenerator
from estate_developer.planning.scheduler import TaskScheduler
from estate_developer.planning.tasks import FarmTask, TaskType
from estate_developer.simulation.reference_rules import (
    MARKET_I0,
    PRODUCTS,
    market_price,
)
from estate_developer.state.parser import (
    FarmState,
    MarketState,
    ObservationState,
    Position,
    PrivateState,
    TownState,
)
from estate_developer.strategic.terminal_value import TerminalValueCalculator


def make_state(*, tiles=None, shed=None, inventories=({},)):
    board = tiles or [[None for _ in range(10)] for _ in range(10)]
    opponent = [[None for _ in range(10)] for _ in range(10)]
    inventory = {item: MARKET_I0 for item in PRODUCTS}
    prices = {item: market_price(item, MARKET_I0) for item in PRODUCTS}
    return ObservationState(
        step=48,
        day=2,
        hour=0,
        player=0,
        remaining_overage_time=60,
        farms=(
            FarmState(2000, board, Position(4, 4), (), ("NW",), 0),
            FarmState(2000, opponent, Position(4, 4), (), ("NW",), 0),
        ),
        private=PrivateState(shed or {}, {}, tuple(inventories)),
        market=MarketState(inventory, prices),
        town=TownState(()),
    )


class TestStrategyCore(unittest.TestCase):
    def test_market_models_match_reference_rules(self):
        manager = MarketManager()
        for product in PRODUCTS:
            for inventory in (9_800, 10_000, 10_200):
                self.assertEqual(
                    manager.calculate_price(product, inventory),
                    market_price(product, inventory),
                )

        sale = simulate_sale("MELON", starting_inventory=10_200, quantity=3)
        self.assertEqual(sale.starting_price, market_price("MELON", 10_200))

    def test_terminal_value_handles_ongoing_crops(self):
        tiles = [[None for _ in range(10)] for _ in range(10)]
        tiles[2][2] = {
            "kind": "PLANT",
            "crop": "TOMATO",
            "planted_day": 0,
            "yield_units": 1,
        }
        value = TerminalValueCalculator.calculate(make_state(tiles=tiles))
        self.assertIsInstance(value, float)

    def test_animal_tasks_and_pickup_route_are_executable(self):
        tiles = [[None for _ in range(10)] for _ in range(10)]
        tiles[4][3] = {
            "kind": "COOP",
            "animal": "GOOSE",
            "fed_today": False,
            "cared_today": False,
            "consecutive_unfed": 1,
            "yield_units": 0,
            "fertilizer_available": False,
        }
        state = make_state(tiles=tiles, shed={"WHEAT": 2})
        tasks = TaskGenerator().generate(state)
        feed = next(task for task in tasks if task.task_type == TaskType.FEED)
        self.assertEqual(
            TaskScheduler().farmer_action(feed, state),
            ["PICKUP", "WHEAT", 1],
        )
        self.assertTrue(any(task.task_type == TaskType.CARE for task in tasks))

    def test_new_production_batch_is_not_a_single_crop_bet(self):
        allocation = ProductionSlotAllocator().crop_portfolio(make_state(), 8)
        self.assertEqual(len(allocation), 8)
        self.assertGreaterEqual(len(set(allocation)), 3)
        self.assertLessEqual(max(allocation.count(crop) for crop in allocation), 4)

    def test_scheduler_moves_one_tile_toward_a_distant_task(self):
        state = make_state()
        # Keep the test independent of the generator's portfolio choice.
        water = FarmTask(TaskType.WATER, 1, target=(2, 4), crop="WHEAT")
        self.assertEqual(TaskScheduler().farmer_action(water, state), ["WEST"])


if __name__ == "__main__":
    unittest.main()
