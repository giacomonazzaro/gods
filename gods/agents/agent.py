from gods.models import Game_State, Choice

class Agent:
    def message(self, msg: str):
        print("Agent:", msg)

    def perform_action(self, game: Game_State, choice: Choice) -> int:
        """Pick an action index. Does NOT call resolve."""
        return 0
