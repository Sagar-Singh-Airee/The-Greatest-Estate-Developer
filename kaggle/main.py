import sys
import traceback

from estate_developer.state.parser import ObservationParser
from estate_developer.opponent.opponent_model import OpponentModel
from estate_developer.strategic.trajectory_planner import (
    StrategicTrajectoryPlanner,
)

opponent_model = OpponentModel()
planner = StrategicTrajectoryPlanner()


def agent(observation, configuration):
    try:
        state = ObservationParser.parse(observation)
        opponent_model.update(state)

        return planner.plan(
            state,
            opponent_model=opponent_model,
        )

    except Exception:
        traceback.print_exc(
            file=sys.stderr
        )

        return {
            "farmer": ["PASS"],
            "hands": [],
            "market": [],
        }
