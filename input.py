from __future__ import annotations
from pyray import *
from models import Card, Stack, Table_State
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


def find_card_at(px: float, py: float, state: Table_State) -> tuple[Card, Stack | None] | None:
    """Find the topmost card at position. Returns (card, stack) or None.
    For loose cards, stack is None."""
    # Check loose cards first (on top of everything)
    for card in reversed(state.loose_cards):
        if point_in_card(px, py, card):
            return (card, None)
    # Check stacks (reverse order so we check top cards first)
    for stack in reversed(state.stacks):
        for card in reversed(stack.cards):
            if point_in_card(px, py, card):
                return (card, stack)
    return None


def find_stack_at(px: float, py: float, state: Table_State) -> Stack | None:
    """Find a stack at the given position."""
    for stack in state.stacks:
        if point_in_stack_area(px, py, stack):
            return stack
    return None


def handle_mouse_press(state: Table_State) -> None:
    """Handle mouse button press - start drag."""
    mx = get_mouse_x()
    my = get_mouse_y()
    drag = state.drag_state

    # Check if clicking a card
    result = find_card_at(mx, my, state)
    if result:
        card, stack = result
        drag.card = card
        drag.source_stack = stack
        drag.offset_x = mx - card.x
        drag.offset_y = my - card.y
        # Remove from source
        if stack:
            gs.remove_card_from_stack(card, stack)
        else:
            gs.remove_loose_card(card, state)


def handle_mouse_release(state: Table_State) -> None:
    """Handle mouse button release - drop card."""
    drag = state.drag_state

    if not drag.card:
        return

    mx = get_mouse_x()
    my = get_mouse_y()

    # Check if dropping on a stack
    target_stack = find_stack_at(mx, my, state)
    if target_stack:
        gs.add_card_to_stack(drag.card, target_stack)
    elif drag.source_stack:
        # Drop as loose card if not on a stack
        gs.add_loose_card(drag.card, state)
    else:
        # Was a loose card, stays loose
        gs.add_loose_card(drag.card, state)

    # Clear drag state
    drag.card = None
    drag.source_stack = None
    drag.offset_x = 0
    drag.offset_y = 0


def handle_mouse_move(state: Table_State) -> None:
    """Update dragged card position."""
    drag = state.drag_state

    if drag.card:
        drag.card.x = get_mouse_x() - drag.offset_x
        drag.card.y = get_mouse_y() - drag.offset_y


def handle_rotate_card(state: Table_State, clockwise: bool = True) -> None:
    """Rotate the card under the cursor by 90 degrees."""
    mx = get_mouse_x()
    my = get_mouse_y()

    result = find_card_at(mx, my, state)
    if result:
        card, _ = result
        if clockwise:
            card.rotation = (card.rotation + 90) % 360
        else:
            card.rotation = (card.rotation - 90) % 360


def update_input(state: Table_State) -> None:
    """Main input processing - call each frame."""
    # Handle mouse
    if is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
        handle_mouse_press(state)
    elif is_mouse_button_released(MouseButton.MOUSE_BUTTON_LEFT):
        handle_mouse_release(state)

    # Update drag position continuously
    handle_mouse_move(state)

    # Handle card rotation
    if is_key_pressed(KeyboardKey.KEY_R):
        if is_key_down(KeyboardKey.KEY_LEFT_SHIFT) or is_key_down(KeyboardKey.KEY_RIGHT_SHIFT):
            handle_rotate_card(state, clockwise=False)
        else:
            handle_rotate_card(state, clockwise=True)
