import unittest

from estate_developer.state.parser import ObservationState, FarmState, PrivateState, MarketState, TownState, Position
from estate_developer.simulation.simulator import Simulator


class TestSimulator(unittest.TestCase):

    def setUp(self):
        # Create a stub state for testing
        self.initial_state = ObservationState(
            step=0,
            day=1,
            hour=6,
            player=0,
            remaining_overage_time=60,
            farms=(
                FarmState(
                    money=100.0,
                    tiles=[[{"kind": "SOIL"} for _ in range(3)] for _ in range(3)],
                    farmer=Position(0, 0),
                    hands=(Position(2, 2),),
                    unlocked_quadrants=("Q1",),
                    hires_today=0
                ),
                FarmState(
                    money=100.0,
                    tiles=[],
                    farmer=Position(0,0),
                    hands=(),
                    unlocked_quadrants=(),
                    hires_today=0
                )
            ),
            private=PrivateState(
                shed={},
                seeds={"WHEAT": 2},
                inventories=({},)
            ),
            market=MarketState(
                inventory={},
                prices={"WHEAT": 25}
            ),
            town=TownState(unlocked_shops=())
        )

    def test_buy_seed_deducts_money_and_adds_seed(self):
        sim = Simulator(self.initial_state)
        sim.step({
            "market": [["BUY_SEED", "WHEAT", 1]],
            "farmer": ["PASS"],
            "hands": [["PASS"]]
        })
        
        state = sim.state
        self.assertEqual(state.me.money, 90.0) # 100 - 10 for wheat
        self.assertEqual(state.private.seeds["WHEAT"], 3) # 2 + 1
        
    def test_plant_seed_reduces_inventory_and_changes_tile(self):
        sim = Simulator(self.initial_state)
        sim.step({
            "farmer": ["PLANT", "WHEAT", 1, 1],
            "hands": [["PASS"]],
            "market": []
        })
        
        state = sim.state
        self.assertEqual(state.private.seeds["WHEAT"], 1) # 2 - 1
        self.assertEqual(state.me.tiles[1][1]["kind"], "PLANT")
        self.assertEqual(state.me.tiles[1][1]["crop"], "WHEAT")
        self.assertEqual(state.me.farmer, Position(1, 1))
        
    def test_harvest_crop_adds_to_inventory(self):
        # Setup a plant ready to harvest
        self.initial_state.me.tiles[1][1] = {
            "kind": "PLANT",
            "crop": "WHEAT",
            "yield_units": 4
        }
        sim = Simulator(self.initial_state)
        sim.step({
            "farmer": ["HARVEST", 1, 1],
            "hands": [["PASS"]],
            "market": []
        })
        
        state = sim.state
        self.assertEqual(state.me.tiles[1][1]["kind"], "SOIL")
        self.assertEqual(state.private.inventories[0].get("WHEAT", 0), 4)

    def test_sell_crop_adds_money_and_reduces_shed(self):
        self.initial_state.private.shed["WHEAT"] = 4
        sim = Simulator(self.initial_state)
        sim.step({
            "market": [["SELL", "WHEAT", 4]],
            "farmer": ["PASS"],
            "hands": [["PASS"]]
        })
        
        state = sim.state
        self.assertEqual(state.me.money, 200.0) # 100 + 4*25
        self.assertEqual(state.private.shed["WHEAT"], 0)

if __name__ == '__main__':
    unittest.main()
