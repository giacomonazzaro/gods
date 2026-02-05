from gods.models import Game_State, Choice

class Agent_Terminal:
    def __init__(self):
        pass

    def message(self, msg: str):
        print("Terminal Agent:", msg)

    def perform_action(self, state: Game_State, choice: Choice) -> int:
        player = state.players[choice.player_index]
        action_list = choice.actions
        if len(action_list.actions) == 0:
            return 0
        elif len(action_list.actions) == 1:
            return 0

        print(f"\n{player.name}, choose an action:")

        # Display options based on action type
        if action_list.type == "main":
            action_labels = {
                "play": "Play a card",
                "pass": "Pass (draw a card)",
                "end": "End the game"
            }
            for i, action in enumerate(action_list.actions):
                label = action_labels.get(action, action)
                print(f"  {i + 1}: {label}")
        elif action_list.type == "choose-binary":
            print(f"  1: Yes")
            print(f"  2: No")
        elif action_list.type == "choose-card":
            from gods.models import Card_Id
            for i, card_id in enumerate(action_list.actions):
                if Card_Id.is_null(card_id):
                    print(f"  {i + 1}: Done")
                else:
                    card = state.get_card(card_id)
                    print(f"  {i + 1}: {card.name}")
        else:
            # Fallback for unknown types
            for i, action in enumerate(action_list.actions):
                print(f"  {i + 1}: {action}")

        num_options = len(action_list.actions) if action_list.type != "choose-binary" else 2
        selected = -1
        while selected not in range(num_options):
            try:
                selected = int(input("Enter choice: "))
                selected -= 1  # Adjust for 0-based index
            except ValueError:
                pass

        return selected