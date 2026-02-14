from __future__ import annotations
import threading

from pyray import *

from gods.models import Game_State, effective_power
from gods.setup import quick_setup
from gods.game import game_loop, compute_player_score
from gods.agents.duel import Agent_Duel
from gods.agents.minimax_stochastic import Agent_Minimax_Stochastic

import kitchen_table.models as kt
from kitchen_table.config import tweak
from kitchen_table.rendering import draw_table, color_from_tuple

from gods_graphical.agent_ui import Agent_UI, update_stacks
from gods_graphical.ui import (
    get_image_path, draw_card_power_badge, draw_buttons, draw_card_highlights,
    draw_player_hud, draw_people_ownership_bars, draw_final_round_indicator,
    draw_game_over_screen,
)


def init_table_state(gods_state: Game_State) -> kt.Table_State:
    cards = []
    gods_cards = []
    stacks = []

    def draw_power(card: kt.Card):
        gods_card = gods_cards[card.id]
        power = str(effective_power(gods_state, gods_card))
        draw_card_power_badge(power, gods_card.destroyed)

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


def draw_hud(gods_state: Game_State, table_state: kt.Table_State):
    for i in range(2):
        player = gods_state.players[i]
        score = compute_player_score(gods_state, i)
        is_current = i == gods_state.current_player
        hud_y = 650 if i == 0 else 260
        draw_player_hud(player.name, score, len(player.deck), is_current, hud_y)

    # People ownership
    people_info = [
        (p.id, p.owner) for p in gods_state.peoples
        if p.owner is not None and not p.destroyed
    ]
    draw_people_ownership_bars(people_info, table_state)

    # Final round indicator
    if gods_state.game_ending and not gods_state.game_over:
        draw_final_round_indicator()


def draw_highlighted_cards(highlighted_cards: list, gods_state: Game_State, table_state: kt.Table_State):
    kt_ids = []
    for card_id in highlighted_cards:
        try:
            card = gods_state.get_card(card_id)
            kt_ids.append(card.id)
        except Exception:
            continue
    draw_card_highlights(kt_ids, table_state)


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
        scores = [compute_player_score(gods_state, 0), compute_player_score(gods_state, 1)]
        names = [gods_state.players[0].name, gods_state.players[1].name]
        if scores[0] > scores[1]:
            result_text = f"{names[0]} wins!"
        elif scores[1] > scores[0]:
            result_text = f"{names[1]} wins!"
        else:
            result_text = "It's a tie!"
        draw_game_over_screen(table_state, result_text, names, scores)

    close_window()


if __name__ == "__main__":
    main()
