from __future__ import annotations

class TournamentHarness:
    """
    Framework for evaluating agents against various adversaries over many matches.
    """

    def __init__(self):
        self.results = []

    def run_match(self, agent1, agent2) -> dict:
        """
        Runs a single match between two agents and returns the result.
        This requires integrating with the actual game environment.
        """
        # Stub
        return {"winner": "agent1", "agent1_score": 1000, "agent2_score": 900}

    def run_tournament(self, primary_agent, adversaries: list, matches_per_adversary: int = 10) -> None:
        """
        Runs a tournament and collects statistics.
        """
        for adv in adversaries:
            wins = 0
            for _ in range(matches_per_adversary):
                res = self.run_match(primary_agent, adv)
                if res["winner"] == "agent1":
                    wins += 1
                self.results.append(res)
            print(f"Vs Adversary: {wins}/{matches_per_adversary} wins")
