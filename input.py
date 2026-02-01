from __future__ import annotations
from pyray import *
from models import Card, Stack, Game_State
from config import tweak
import game_state as gs


def point_in_card(px: float, py: float, card: Card) -> bool:
    """Check if point (px, py) is inside the card bounds."""
    w = tweak["card_width"]
    h = tweak["card_height"]
    return (card.x <= px <= card.x + w and card.y <= py <= card.y + h)


def point_in_stack_area(px: float, py: float, stack: Stack) -> bool:
    """Check if point is in the stack's general area (for drop targets)."""
    w = tweak["card_width"]
    h = tweak["card_height"]

    if stack.cards:
        # Calculate bounds including all cards in stack
        last_card = stack.cards[-1]
        max_x = last_card.x + w
        max_y = last_card.y + h
        return (stack.x <= px <= max_x and stack.y <= py <= max_y)
    else:
        # Empty stack - just check base position
        return (stack.x <= px <= stack.x + w and stack.y <= py <= stack.y + h)


def find_card_at(px: float, py: float, game_state: Game_State) -> tuple[Card, Stack | None] | None:
    """Find the topmost card at position. Returns (card, stack) or None.
    For table cards, stack is None."""
    # Check table cards first (on top of everything)
    for card in reversed(game_state.table_cards):
        if point_in_card(px, py, card):
            return (card, None)  # None indicates table card
    # Check hand
    for card in reversed(game_state.hand.cards):
        if point_in_card(px, py, card):
            return (card, game_state.hand)
    return None


def point_in_table_area(px: float, py: float) -> bool:
    """Check if point is in the table area (where cards can be dropped)."""
    tx, ty, tw, th = tweak["table_area"]
    return tx <= px <= tx + tw and ty <= py <= ty + th


def point_in_hand_area(px: float, py: float, game_state: Game_State) -> bool:
    """Check if point is in the hand area."""
    return point_in_stack_area(px, py, game_state.hand)


def is_draw_pile_clicked(px: float, py: float, game_state: Game_State) -> bool:
    """Check if the draw pile was clicked."""
    stack = game_state.draw_pile
    w = tweak["card_width"]
    h = tweak["card_height"]

    if stack.cards:
        # Check topmost card of draw pile
        top_card = stack.cards[-1]
        return point_in_card(px, py, top_card)
    else:
        # Empty pile placeholder
        return (stack.x <= px <= stack.x + w and stack.y <= py <= stack.y + h)


def handle_mouse_press(game_state: Game_State) -> None:
    """Handle mouse button press - start drag or click draw pile."""
    mx = get_mouse_x()
    my = get_mouse_y()
    drag = game_state.drag_state

    # Check if clicking draw pile
    if is_draw_pile_clicked(mx, my, game_state):
        gs.draw_cards(game_state, 1)
        return

    # Check if clicking a draggable card
    result = find_card_at(mx, my, game_state)
    if result:
        card, stack = result
        drag.card = card
        drag.source_stack = stack  # None for table cards
        drag.offset_x = mx - card.x
        drag.offset_y = my - card.y
        # Remove from source
        if stack:
            gs.remove_card_from_stack(card, stack)
        else:
            gs.remove_card_from_table(card, game_state)


def handle_mouse_release(game_state: Game_State) -> None:
    """Handle mouse button release - drop card."""
    drag = game_state.drag_state

    if not drag.card:
        return

    mx = get_mouse_x()
    my = get_mouse_y()

    # Check if dropping back on hand area
    if point_in_hand_area(mx, my, game_state):
        gs.add_card_to_stack(drag.card, game_state.hand)
    # Check if dropping on table area
    elif point_in_table_area(mx, my):
        # Card keeps its current position on the table
        gs.add_card_to_table(drag.card, game_state)
    elif drag.source_stack:
        # Return to source stack if dropped outside valid areas
        gs.add_card_to_stack(drag.card, drag.source_stack)
    else:
        # Was a table card, put it back on table
        gs.add_card_to_table(drag.card, game_state)

    # Clear drag state
    drag.card = None
    drag.source_stack = None
    drag.offset_x = 0
    drag.offset_y = 0


def handle_mouse_move(game_state: Game_State) -> None:
    """Update dragged card position."""
    drag = game_state.drag_state

    if drag.card:
        drag.card.x = get_mouse_x() - drag.offset_x
        drag.card.y = get_mouse_y() - drag.offset_y


def update_input(game_state: Game_State) -> None:
    """Main input processing - call each frame."""
    # Handle mouse
    if is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
        handle_mouse_press(game_state)
    elif is_mouse_button_released(MouseButton.MOUSE_BUTTON_LEFT):
        handle_mouse_release(game_state)

    # Update drag position continuously
    handle_mouse_move(game_state)

    # Keyboard: R to end turn
    if is_key_pressed(KeyboardKey.KEY_R):
        gs.end_turn(game_state)
