from gods.agents.agent import Agent
from gods.models import Game_State, Choice, Card_Id
from kitchen_table.models import Table_State
from gods.game import *
from kitchen_table.config import tweak
from pyray import *
import time

def point_in_rect(mx: float, my: float, x: float, y: float, w: float, h: float) -> bool:
    return x <= mx <= x + w and y <= my <= y + h

def update_stacks(table_state: Table_State, gods_state: Game_State):
    from kitchen_table.game_state import update_card_positions
    def update_stack(stack_id: int, card_list: list[Card]):
        table_state.stacks[stack_id].cards = [card.id for card in card_list]
        update_card_positions(table_state.stacks[stack_id], table_state)

    # Player 1 areas (bottom)
    update_stack(0, gods_state.players[0].deck)
    update_stack(1, gods_state.players[0].hand)
    update_stack(2, gods_state.players[0].discard)
    update_stack(3, gods_state.players[0].wonders)

    # Player 2 areas (top)
    update_stack(4, gods_state.players[1].deck)
    update_stack(5, gods_state.players[1].hand)
    update_stack(6, gods_state.players[1].discard)
    update_stack(7, gods_state.players[1].wonders)

    # People cards (center)
    update_stack(8, gods_state.peoples)

@dataclass
class Button:
    x: int
    y: int
    width: int
    height: int
    text: str = ""

    def pressed(self, mx, my, click) -> bool:
        if not click:
            return False
        return point_in_rect(mx, my, self.x, self.y, self.width, self.height)




class Agent_UI(Agent):
    def __init__(self, table_state: Table_State):
        self.table_state = table_state
        self.highlighted_cards = []
        self.buttons = []

    def message(self, msg: str):
        pass

    def choose_action(self, state: Game_State, choice: Choice, actions: list) -> int:
        if len(actions) == 0:
            return 0
        elif len(actions) == 1:
            return 0

        mx, my = get_mouse_x(), get_mouse_y()
        click = is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT)

        # Display options based on action type
        count = len(actions)
        button_w = 140
        button_h = 45
        gap = 20
        total_width = count * button_w + (count - 1) * gap
        start_x = (tweak["window_width"] - total_width) // 2
        button_y = tweak["window_height"] - 50

        if choice.type == "main":
            self.buttons = []
            for i, action in enumerate(actions):
                x = start_x + i * (button_w + gap)
                button = Button(x, button_y, button_w, button_h, text=str(action))
                self.buttons.append(button)

        elif choice.type == "choose-binary":
            self.buttons = []
            labels = ["Yes", "No"]
            for i in range(2):
                x = start_x + i * (button_w + gap)
                button = Button(x, button_y, button_w, button_h, text=labels[i])
                self.buttons.append(button)
        elif choice.type == "choose-card":
            self.highlighted_cards = []
            self.buttons = []
            for i, card_id in enumerate(actions):
                if Card_Id.is_null(card_id):
                    x = start_x
                    button = Button(x, button_y, button_w, button_h, text="Done")
                    self.buttons.append(button)
                else:
                    card = state.get_card(card_id)
                    kt_card = self.table_state.animated_cards[card.id]
                    self.highlighted_cards.append(card_id)

        selected = -1
        while selected == -1:
            time.sleep(1/60)  # Yield the GIL so the render thread can run
            mx, my = get_mouse_x(), get_mouse_y()
            click = is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT)
            if choice.type == "main":
                for i, action in enumerate(actions):
                    if self.buttons[i].pressed(mx, my, click):
                        selected = i
                        break
            elif choice.type == "choose-binary":
                for i in range(2):
                    if self.buttons[i].pressed(mx, my, click):
                        selected = i
                        break
            elif choice.type == "choose-card":
                for i, card_id in enumerate(actions):
                    if Card_Id.is_null(card_id):
                        if self.buttons[0].pressed(mx, my, click):
                            selected = i
                            break
                    else:
                        card = state.get_card(card_id)
                        kt_card = self.table_state.cards[card.id]
                        w = tweak["card_width"]
                        h = tweak["card_height"]
                        if click and point_in_rect(mx, my, kt_card.x, kt_card.y, w, h):
                            selected = i
                            break

        update_stacks(self.table_state, state)
        self.highlighted_cards = []
        self.buttons = []
        return selected
