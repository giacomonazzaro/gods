from gods.models import Game_State, Choice
import random

class Agent_Random:
    def __init__(self):
        pass

    def message(self, msg: str):
        pass  # Silent agent

    def perform_action(self, state: Game_State, choice: Choice) -> int:
        action_list = choice.actions
        if len(action_list.actions) == 0:
            return 0
        if len(action_list.actions) == 1:
            return 0

        return random.randint(0, len(action_list.actions) - 1)
