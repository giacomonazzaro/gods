from __future__ import annotations
import os
import threading

from pyray import *

from gods.models import Game_State, Card, effective_power
from gods.setup import quick_setup
from gods.game import game_loop, compute_player_score
from gods.agents.duel import Agent_Duel
from gods.agents.minimax_stochastic import Agent_Minimax_Stochastic

import kitchen_table.models as kt
from kitchen_table.config import tweak
from kitchen_table.rendering import draw_table, color_from_tuple

from gods_graphical.agent_ui import Agent_UI, update_stacks

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "gods", "cards", "card-images")


def get_image_path(card_name: str) -> str | None:
    filename = card_name.lower().replace(" ", "_") + ".jpg"
    path = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(path):
        return path
    return None


def init_table_state(gods_state: Game_State) -> kt.Table_State:
    cards = []
    gods_cards = []
    stacks = []

    def draw_power(card: kt.Card):
        w = tweak["card_width"]
        h = tweak["card_height"]
        r = tweak["card_corner_radius"]
        gods_card = gods_cards[card.id]
        power = str(effective_power(gods_state, gods_card))

        draw_circle(
            int(0.88 * w), int(0.12 * w), int(0.12 * w), Color(255, 255, 255, 255)
        )
        draw_text(
            power, int(0.83 * w), int(0.03 * w), int(0.2 * w), Color(0, 0, 0, 255)
        )

        if gods_card.destroyed:
            draw_rectangle_rounded(
                Rectangle(0, 0, w, h), r / min(w, h), 8, (0, 0, 0, 100)
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
                draw_callback=draw_power,
            )
            card.id = card_id
            card_list[i].kt_card_id = card_id
            cards.append(kt_card)
            gods_cards.append(card)
            stack_card_indices.append(card_id)

        stack = kt.Stack(
            x=stack_x, y=stack_y,
            cards=stack_card_indices,
            spread_x=spread_x, spread_y=spread_y,
            face_up=face_up,
        )
        stacks.append(stack)

    # Layout from config
    deck_x = tweak["deck_x"]
    discard_x = tweak["discard_x"]
    hand_x = tweak["hand_x"]
    wonders_x = tweak["wonders_x"]
    peoples_x = tweak["peoples_x"]

    p1_hand_y = tweak["player1_hand_y"]
    p1_deck_y = tweak["player1_deck_y"]
    p1_wonders_y = tweak["player1_wonders_y"]

    p2_hand_y = tweak["player2_hand_y"]
    p2_deck_y = tweak["player2_deck_y"]
    p2_wonders_y = tweak["player2_wonders_y"]

    peoples_y = tweak["peoples_y"]

    spread_hand = tweak["hand_spread_x"]
    spread_wonders = tweak["wonders_spread_x"]
    spread_pile = tweak["pile_spread_y"]

    # Player 1 areas (bottom)
    add_cards_from_list(gods_state.players[0].deck, deck_x, p1_deck_y, spread_y=spread_pile, face_up=False)
    add_cards_from_list(gods_state.players[0].hand, hand_x, p1_hand_y, spread_x=spread_hand)
    add_cards_from_list(gods_state.players[0].discard, discard_x, p1_deck_y, spread_y=spread_pile)
    add_cards_from_list(gods_state.players[0].wonders, wonders_x, p1_wonders_y, spread_x=spread_wonders)

    # Player 2 areas (top)
    add_cards_from_list(gods_state.players[1].deck, deck_x, p2_deck_y, spread_y=spread_pile, face_up=False)
    add_cards_from_list(gods_state.players[1].hand, hand_x, p2_hand_y, spread_x=spread_hand, face_up=False)
    add_cards_from_list(gods_state.players[1].discard, discard_x, p2_deck_y, spread_y=spread_pile)
    add_cards_from_list(gods_state.players[1].wonders, wonders_x, p2_wonders_y, spread_x=spread_wonders)

    # People cards (center)
    add_cards_from_list(gods_state.peoples, peoples_x, peoples_y, spread_x=spread_wonders)

    return kt.Table_State(cards=cards, stacks=stacks)


# --- HUD rendering ---

OWNER_COLORS = [
    (100, 200, 100, 200),  # Player 0 - green
    (200, 100, 100, 200),  # Player 1 - red
]


def draw_people_ownership(gods_state: Game_State, table_state: kt.Table_State):
    if not table_state.animated_cards:
        return
    w = tweak["card_width"]
    h = tweak["card_height"]
    for people in gods_state.peoples:
        if people.owner is not None and not people.destroyed:
            kt_card = table_state.animated_cards[people.id]
            draw_rectangle_rounded(
                Rectangle(kt_card.x + 4, kt_card.y + h - 12, w - 8, 8),
                0.5, 4, OWNER_COLORS[people.owner],
            )


def draw_hud(gods_state: Game_State, table_state: kt.Table_State):
    w_width = tweak["window_width"]

    for i in range(2):
        player = gods_state.players[i]
        score = compute_player_score(gods_state, i)
        deck_count = len(player.deck)
        is_current = i == gods_state.current_player

        hud_y = 650 if i == 0 else 260

        # Current player indicator bar
        if is_current:
            indicator_color = color_from_tuple(tweak["current_player_color"])
            draw_rectangle_rounded(
                Rectangle(10, hud_y - 5, 6, 50), 0.5, 4, indicator_color
            )

        # Player name
        name_color = color_from_tuple(tweak["current_player_color"]) if is_current else Color(255, 255, 255, 255)
        draw_text(player.name, 25, hud_y, 24, name_color)

        # Score
        draw_text(f"Score: {score}", 25, hud_y + 28, 20, Color(200, 200, 200, 255))

        # Deck count above/below deck stack
        deck_x = tweak["deck_x"]
        deck_y = tweak["player1_deck_y"] if i == 0 else tweak["player2_deck_y"]
        draw_text(
            str(deck_count),
            deck_x + tweak["card_width"] // 2 - 10,
            deck_y - 22,
            18,
            Color(180, 180, 180, 255),
        )

    # People ownership indicators
    draw_people_ownership(gods_state, table_state)

    # Final round indicator
    if gods_state.game_ending and not gods_state.game_over:
        text = "FINAL ROUND"
        text_w = measure_text(text, 24)
        draw_text(
            text, (w_width - text_w) // 2, tweak["peoples_y"] - 30, 24,
            Color(255, 180, 0, 200),
        )


# --- Button and highlight rendering ---

def draw_buttons(buttons: list):
    mx, my = get_mouse_x(), get_mouse_y()
    for button in buttons:
        hovered = (button.x <= mx <= button.x + button.width
                   and button.y <= my <= button.y + button.height)
        color_key = "button_hover_color" if hovered else "button_color"
        color = color_from_tuple(tweak[color_key])
        draw_rectangle_rounded(
            Rectangle(button.x, button.y, button.width, button.height), 0.3, 8, color
        )
        text_width = measure_text(button.text, 20)
        text_x = button.x + (button.width - text_width) // 2
        text_y = button.y + (button.height - 20) // 2
        draw_text(button.text, text_x, text_y, 20, color_from_tuple(tweak["button_text_color"]))


def draw_highlighted_cards(highlighted_cards: list, gods_state: Game_State, table_state: kt.Table_State):
    if not table_state.animated_cards:
        return
    w = tweak["card_width"]
    h = tweak["card_height"]
    highlight_color = color_from_tuple(tweak["highlight_color"])
    for card_id in highlighted_cards:
        try:
            card = gods_state.get_card(card_id)
        except Exception:
            continue
        kt_card = table_state.animated_cards[card.id]
        draw_rectangle_rounded_lines_ex(
            Rectangle(kt_card.x, kt_card.y, w, h), 0.25, 8, 4, highlight_color
        )


# --- Game over screen ---

def draw_game_over(gods_state: Game_State, table_state: kt.Table_State):
    scores = [compute_player_score(gods_state, 0), compute_player_score(gods_state, 1)]
    if scores[0] > scores[1]:
        result_text = f"{gods_state.players[0].name} wins!"
    elif scores[1] > scores[0]:
        result_text = f"{gods_state.players[1].name} wins!"
    else:
        result_text = "It's a tie!"

    w_width = tweak["window_width"]
    w_height = tweak["window_height"]

    while not window_should_close():
        begin_drawing()
        clear_background(color_from_tuple(tweak["background_color"]))
        draw_table(table_state)

        # Semi-transparent overlay
        draw_rectangle(0, 0, w_width, w_height, color_from_tuple(tweak["modal_overlay"]))

        title_w = measure_text("GAME OVER", 60)
        draw_text("GAME OVER", (w_width - title_w) // 2, 350, 60, Color(255, 255, 255, 255))

        result_w = measure_text(result_text, 40)
        draw_text(result_text, (w_width - result_w) // 2, 430, 40, Color(255, 215, 0, 255))

        score_text = f"{gods_state.players[0].name}: {scores[0]}  |  {gods_state.players[1].name}: {scores[1]}"
        score_w = measure_text(score_text, 30)
        draw_text(score_text, (w_width - score_w) // 2, 490, 30, Color(200, 200, 200, 255))

        end_drawing()


# --- Main ---

def main():
    gods_state = quick_setup()
    table_state = init_table_state(gods_state)
    table_state.draw_callback = lambda table: draw_hud(gods_state, table_state)

    set_config_flags(ConfigFlags.FLAG_WINDOW_HIGHDPI)
    init_window(tweak["window_width"], tweak["window_height"], tweak["window_title"])
    set_target_fps(tweak["target_fps"])

    agent_ui = Agent_UI(table_state)
    agent_ai = Agent_Minimax_Stochastic()
    agent = Agent_Duel(agent_ui, agent_ai)

    def display(state: Game_State):
        update_stacks(table_state, gods_state)

    def game_loop_thread():
        game_loop(gods_state, agent, display)

    game_thread = threading.Thread(target=game_loop_thread, daemon=True)
    game_thread.start()

    # Render loop
    while not window_should_close():
        if gods_state.game_over:
            break

        begin_drawing()
        clear_background(color_from_tuple(tweak["background_color"]))
        draw_table(table_state)
        draw_buttons(agent_ui.buttons)
        draw_highlighted_cards(agent_ui.highlighted_cards, gods_state, table_state)
        end_drawing()

    # Game over screen
    if gods_state.game_over:
        update_stacks(table_state, gods_state)
        draw_game_over(gods_state, table_state)

    close_window()


if __name__ == "__main__":
    main()
