from gods.game import Game_State, Choice

class Agent:
    def message(self, msg: str):
        print("Agent:", msg)

    def perform_action(self, game: Game_State, choice: Choice):
        pass