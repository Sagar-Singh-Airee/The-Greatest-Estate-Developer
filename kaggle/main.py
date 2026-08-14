import sys
import traceback
from estate_developer.state.parser import parse_observation
from estate_developer.opponent.opponent_model import OpponentModel
from estate_developer.strategic.trajectory_planner import StrategicTrajectoryPlanner

# Initialize global state tracking across turns
opponent_model = OpponentModel()
planner = StrategicTrajectoryPlanner()

def agent(observation, configuration):
    """
    Kaggle environment entry point for The Greatest Estate Developer agent.
    """
    try:
        # 1. Parse the Kaggle dictionary into our ObservationState
        state = parse_observation(observation)
        
        # 2. Update our opponent model with the fresh state
        opponent_model.update(state)
        
        # 3. Request the best action from the V10 trajectory planner
        actions = planner.plan(state, opponent_model=opponent_model)
        
        return actions
        
    except Exception as e:
        # Fallback to PASS in case of a fatal error to avoid disqualification
        traceback.print_exc(file=sys.stderr)
        return {"farmer": ["PASS"], "hands": [], "market": []}
