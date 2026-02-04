from __future__ import annotations
from typing import Optional
from pyray import *
from config import tweak
from gods.models import Card as Gods_Card, Card_Type, Game_State
from gods_ui import Gods_UI


class Input_Result:
    """Result of processing input for a frame."""
    def __init__(self):
        self.play_card: Optional[Gods_Card] = None
        self.pass_turn: bool = False
        self.end_game: bool = False


def point_in_rect(mx: float, my: float, x: float, y: float, w: float, h: float) -> bool:
    return x <= mx <= x + w and y <= my <= y + h


def find_hand_card_at(mx: float, my: float, game: Game_State) -> Optional[Gods_Card]:
    """Find if mouse is over a card in the current player's hand."""
    player = game.active_player()
    player_idx = game.current_player

    w = tweak["card_width"]
    h = tweak["card_height"]
    y_hand = tweak["player1_hand_y"] if player_idx == 0 else tweak["player2_hand_y"]

    # Check in reverse order for proper z-order (top cards first)
    for i in range(len(player.hand) - 1, -1, -1):
        x = tweak["hand_x"] + i * tweak["hand_spread_x"]
        if point_in_rect(mx, my, x, y_hand, w, h):
            return player.hand[i]

    return None


def check_pass_button(mx: float, my: float) -> bool:
    """Check if mouse is over the Pass button."""
    return point_in_rect(mx, my, 50, tweak["ui_y"],
                         tweak["button_width"], tweak["button_height"])


def check_end_button(mx: float, my: float) -> bool:
    """Check if mouse is over the End Game button."""
    return point_in_rect(mx, my, 190, tweak["ui_y"],
                         tweak["button_width"], tweak["button_height"])


def update_hover_states(ui: Gods_UI, game: Game_State) -> None:
    """Update button hover states based on mouse position."""
    mx, my = get_mouse_x(), get_mouse_y()

    ui.ui_state["pass_hovered"] = check_pass_button(mx, my)
    ui.ui_state["end_hovered"] = check_end_button(mx, my) and not game.game_ending


def process_input(game: Game_State, ui: Gods_UI) -> Input_Result:
    """Process input for a single frame. Returns actions to take."""
    result = Input_Result()

    if game.game_over:
        return result

    mx, my = get_mouse_x(), get_mouse_y()

    # Update hover states
    update_hover_states(ui, game)

    # Process clicks
    if is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
        # Check if clicking a card in hand
        card = find_hand_card_at(mx, my, game)
        if card and card.card_type != Card_Type.PEOPLE:
            result.play_card = card
            return result

        # Check pass button
        if check_pass_button(mx, my):
            result.pass_turn = True
            return result

        # Check end game button
        if check_end_button(mx, my) and not game.game_ending:
            result.end_game = True
            return result

    return result
