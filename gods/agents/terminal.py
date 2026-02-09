from gods.models import Game_State, Choice

class Agent_Terminal:
    def __init__(self):
        pass

    def message(self, msg: str):
        print("Terminal Agent:", msg)

    def choose_action(self, state: Game_State, choice: Choice, actions: list) -> int:
        player = state.players[choice.player_index]
        if len(actions) == 0:
            return 0
        elif len(actions) == 1:
            return 0

        print(f"\n{player.name}, choose an action:")

        # Display options based on action type
        if choice.type == "main":
            action_labels = {
                "play": "Play a card",
                "pass": "Pass (draw a card)",
                "end": "End the game"
            }
            for i, action in enumerate(actions):
                label = action_labels.get(action, action)
                print(f"  {i + 1}: {label}")
        elif choice.type == "choose-binary":
            print(f"  1: Yes")
            print(f"  2: No")
        elif choice.type == "choose-card":
            from gods.models import Card_Id
            for i, card_id in enumerate(actions):
                if Card_Id.is_null(card_id):
                    print(f"  {i + 1}: Done")
                else:
                    card = state.get_card(card_id)
                    print(f"  {i + 1}: {card.name}")
        else:
            # Fallback for unknown types
            for i, action in enumerate(actions):
                print(f"  {i + 1}: {action}")

        num_options = len(actions) if choice.type != "choose-binary" else 2
        selected = -1
        while selected not in range(num_options):
            try:
                selected = int(input("Enter choice: "))
                selected -= 1  # Adjust for 0-based index
            except ValueError:
                pass

        return selected
