from gods.models import Game_State, Choice
from gods.agents.agent import Agent

class Agent_Duel(Agent):
    def __init__(self, agent_0, agent_1):
        self.agents = [agent_0, agent_1]

    def message(self, msg: str):
        print("Duel:", msg)

    def perform_action(self, state: Game_State, choice: Choice):
        return self.agents[choice.player_index].perform_action(state, choice)