from __future__ import annotations
from turtle import st
from gods.models import Game_State, Card, effective_power
from gods.setup import quick_setup
import kitchen_table.models as kt
from gods.agents.duel import Agent_Duel
from gods.agents.terminal import Agent_Terminal
from gods.agents.mcts import Agent_MCTS
from gods.game import game_loop, display_game_state, compute_player_score
from kitchen_table.config import tweak

gods_state = quick_setup()


def init_table_state(gods_state: Game_State) -> kt.Table_State:
    import os

    cards = []
    gods_cards = []
    stacks = []

    # Path to card images
    images_dir = os.path.join(os.path.dirname(__file__), "..", "gods", "cards", "card-images")

    def get_image_path(card_name: str) -> str | None:
        """Get image path for a card, or None if not found."""
        # Convert card name to lowercase and replace spaces with underscores
        filename = card_name.lower().replace(" ", "_") + ".jpg"
        path = os.path.join(images_dir, filename)
        if os.path.exists(path):
            return path
        return None

    def draw_power(card: kt.Card):
        w: int = tweak["card_width"]
        h = tweak["card_height"]
        r = tweak["card_corner_radius"]
        gods_card = gods_cards[card.id]
        power = str(effective_power(gods_state, gods_card))
        
        draw_circle(
            int(0.88 * w), int(0.12 * w), int(0.12 * w), Color(255, 255, 255, 255)
        )

        draw_text(
            power,
            int(0.83 * w),
            int(0.03 * w),
            int(0.2 * w),
            Color(0,0,0,255)
        )

        if gods_card.destroyed:
            draw_rectangle_rounded(
                Rectangle(0, 0, w, h), r / min(w, h), 8,
                (0, 0, 0, 100)
            )

    def add_cards_from_list(card_list, stack_x, stack_y, spread_x=0.0, spread_y=0.0, face_up=True):
        stack_card_indices = []
        for i, card in enumerate(card_list):
            card_id = len(cards)
            kt_card = kt.Card(
                id=card_id,
                title=card.name,
                description=card.effect,
                image_path=get_image_path(card.name),
                x=stack_x + i * spread_x,
                y=stack_y + i * spread_y,
                draw_callback=draw_power
            )
            card.id = card_id
            card_list[i].kt_card_id = card_id  # Link back to kitchen_table card index
            cards.append(kt_card)
            gods_cards.append(card)
            stack_card_indices.append(card_id)

        stack = kt.Stack(
            x=stack_x,
            y=stack_y,
            cards=stack_card_indices,
            spread_x=spread_x,
            spread_y=spread_y,
            face_up=face_up,
        )
        stacks.append(stack)

    # Layout positions
    discard_x = 50      # leftmost
    deck_x = 300        # right of discard
    hand_x = 600        # centered
    wonders_x = 800     # centered
    peoples_x = 30     # centered

    p1_hand_y = 740     # bottom
    p1_deck_y = 740     # above hand
    p1_wonders_y = 500  # below center

    p2_hand_y = 20      # top
    p2_deck_y = 20     # below hand
    p2_wonders_y = 250

    peoples_y = 380     # center

    spread_hand = tweak["hand_spread_x"]
    spread_wonders = 160
    spread_pile = tweak["pile_spread_y"]

    # Player 1 areas (bottom)
    add_cards_from_list(gods_state.players[0].deck, deck_x, p1_deck_y, spread_y=spread_pile, face_up=False)
    add_cards_from_list(gods_state.players[0].hand, hand_x, p1_hand_y, spread_x=spread_hand)
    add_cards_from_list(gods_state.players[0].discard, discard_x, p1_deck_y, spread_y=spread_pile)
    add_cards_from_list(gods_state.players[0].wonders, wonders_x, p1_wonders_y, spread_x=spread_wonders)

    # Player 2 areas (top)
    add_cards_from_list(gods_state.players[1].deck, deck_x, p2_deck_y, spread_y=spread_pile, face_up=False)
    add_cards_from_list(gods_state.players[1].hand, hand_x, p2_hand_y, spread_x=spread_hand)
    add_cards_from_list(gods_state.players[1].discard, discard_x, p2_deck_y, spread_y=spread_pile)
    add_cards_from_list(gods_state.players[1].wonders, wonders_x, p2_wonders_y, spread_x=spread_wonders)

    # People cards (center)
    add_cards_from_list(gods_state.peoples, peoples_x, peoples_y, spread_x=spread_wonders)

    return kt.Table_State(cards=cards, stacks=stacks)


from gods_graphical.agent_ui import update_stacks

def update_powers(gods_state: Game_State, table_state: kt.Table_State):
    for card in gods_state.peoples + gods_state.players[0].wonders + gods_state.players[1].wonders + gods_state.players[0].hand + gods_state.players[1].hand:
        power = effective_power(gods_state, card)
        table_state.cards[card.id].title = f"{card.name} [{power}]"


def table_draw_callback(table: kt.Table_State):
    points = compute_player_score(gods_state, 0) 
    draw_text(
        f"points: {points}",
        90,
        650,
        40,
        Color(255, 255, 255,255)
    )
    
    points = compute_player_score(gods_state, 1) 
    draw_text(
        f"points: {points}",
        90,
        280,
        40,
        Color(255, 255, 255,255)
    )
    
    

table_state = init_table_state(gods_state)
table_state.draw_callback = table_draw_callback

from pyray import *
from kitchen_table.config import tweak
from kitchen_table.rendering import draw_table, color_from_tuple
from kitchen_table.input import update_input



# Initialize window
init_window(
    tweak["window_width"],
    tweak["window_height"],
    tweak["window_title"]
)
set_target_fps(tweak["target_fps"])

from gods_graphical.agent_ui import Agent_UI
agent_ui = Agent_UI(table_state)
agent_mcts = Agent_MCTS()
agent = Agent_Duel(agent_ui, agent_mcts)

import threading

# Main loop
def display(state: Game_State):
    update_stacks(table_state, gods_state)
    update_powers(gods_state, table_state)
    # display_game_state(state)

def game_loop_thread():
    game_loop(gods_state, agent, display)

game_thread = threading.Thread(target=game_loop_thread, daemon=True)
game_thread.start()

while not window_should_close():
    begin_drawing()
    clear_background(color_from_tuple(tweak["background_color"]))
    draw_table(table_state)

    for button in agent.agents[0].buttons:
        color = color_from_tuple(tweak["button_color"])
        draw_rectangle_rounded(
            Rectangle(button.x, button.y, button.width, button.height), 0.3, 8, color
        )
        text_width = measure_text(button.text, 20)
        text_x = button.x + (button.width - text_width) // 2
        text_y = button.y + (button.height - 20) // 2
        draw_text(button.text, text_x, text_y, 20, color_from_tuple(tweak["button_text_color"]))

    for card_id in agent.agents[0].highlighted_cards:
        try:
            card = gods_state.get_card(card_id)
        except:
            continue
        kt_card = table_state.cards[card.id]
        w = tweak["card_width"]
        h = tweak["card_height"]
        draw_rectangle_rounded_lines_ex(
            Rectangle(kt_card.x, kt_card.y, w, h), 0.25, 8, 4, (255, 255, 255, 100)
        )

    end_drawing()
    

# Cleanup
close_window()
