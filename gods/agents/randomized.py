from gods.models import Game_State, Choice
import random

class Agent_Random:
    def __init__(self):
        pass

    def message(self, msg: str):
        pass  # Silent agent

    def choose_action(self, state: Game_State, choice: Choice, actions: list) -> int:
        if len(actions) == 0:
            return 0
        if len(actions) == 1:
            return 0

        return random.randint(0, len(actions) - 1)
