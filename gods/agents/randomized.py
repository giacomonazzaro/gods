from gods.models import Game_State, Choice
import random

class Agent_Random:
    def __init__(self):
        pass

    def message(self, msg: str):
        pass  # Silent agent

    def perform_action(self, state: Game_State, choice: Choice):
        action_list = choice.actions
        if len(action_list.actions) == 0:
            return
        if len(action_list.actions) == 1:
            choice.resolve(state, choice, 0, self)
            return

        selected = random.randint(0, len(action_list.actions) - 1)
        choice.resolve(state, choice, selected, self)
        return selected
