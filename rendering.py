from pyray import *
from models import Card, Stack, Table_State
from config import tweak


def color_from_tuple(c: tuple) -> Color:
    """Convert RGBA tuple to raylib Color."""
    return Color(c[0], c[1], c[2], c[3])


def draw_card_back(x: float, y: float) -> None:
    """Draw a face-down card."""
    w = tweak["card_width"]
    h = tweak["card_height"]
    r = tweak["card_corner_radius"]

    # Card background
    draw_rectangle_rounded(
        Rectangle(x, y, w, h), r / min(w, h), 8,
        color_from_tuple(tweak["card_back"])
    )

    # Simple pattern on back
    pattern_color = color_from_tuple(tweak["card_back_pattern"])
    margin = 15
    draw_rectangle_rounded(
        Rectangle(x + margin, y + margin, w - 2*margin, h - 2*margin),
        r / min(w, h), 8, pattern_color
    )

    # Border
    draw_rectangle_rounded_lines_ex(
        Rectangle(x, y, w, h), r / min(w, h), 8, 2,
        color_from_tuple(tweak["card_border"])
    )


def draw_card_content(x: float, y: float, card: Card, face_up: bool) -> None:
    """Draw card content at origin (used for rotation)."""
    if not face_up:
        draw_card_back(x, y)
        return

    w = tweak["card_width"]
    h = tweak["card_height"]
    r = tweak["card_corner_radius"]
    padding = tweak["card_padding"]

    # Card background
    draw_rectangle_rounded(
        Rectangle(x, y, w, h), r / min(w, h), 8,
        color_from_tuple(tweak["card_background"])
    )

    # Border
    draw_rectangle_rounded_lines_ex(
        Rectangle(x, y, w, h), r / min(w, h), 8, 2,
        color_from_tuple(tweak["card_border"])
    )

    # Title
    title_size = tweak["title_font_size"]
    draw_text(
        card.title,
        int(x + padding),
        int(y + padding),
        title_size,
        color_from_tuple(tweak["card_title_color"])
    )

    # Description (with simple word wrapping)
    if card.description:
        desc_size = tweak["description_font_size"]
        desc_y = y + padding + title_size + 10
        max_width = w - 2 * padding

        # Simple word wrapping
        words = card.description.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            text_width = measure_text(test_line, desc_size)
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for i, line in enumerate(lines):
            draw_text(
                line,
                int(x + padding),
                int(desc_y + i * (desc_size + 2)),
                desc_size,
                color_from_tuple(tweak["card_description_color"])
            )


def draw_card(card: Card, face_up: bool = True) -> None:
    """Draw a single card at its position, with rotation support."""
    w = tweak["card_width"]
    h = tweak["card_height"]

    if card.rotation == 0:
        draw_card_content(card.x, card.y, card, face_up)
    else:
        # Calculate center of card
        cx = card.x + w / 2
        cy = card.y + h / 2

        # Apply rotation around center
        rl_push_matrix()
        rl_translatef(cx, cy, 0)
        rl_rotatef(card.rotation, 0, 0, 1)
        rl_translatef(-cx, -cy, 0)

        draw_card_content(card.x, card.y, card, face_up)

        rl_pop_matrix()


def draw_stack(stack: Stack, state: Table_State) -> None:
    """Draw all cards in a stack."""
    for card_id in stack.cards:
        card = state.cards[card_id]
        draw_card(card, face_up=stack.face_up)


def draw_stack_placeholder(stack: Stack, label: str) -> None:
    """Draw an empty stack placeholder with label."""
    w = tweak["card_width"]
    h = tweak["card_height"]
    r = tweak["card_corner_radius"]

    # Dashed outline placeholder
    draw_rectangle_rounded_lines_ex(
        Rectangle(stack.x, stack.y, w, h), r / min(w, h), 8, 1,
        Color(100, 100, 100, 100)
    )

    # Label
    text_width = measure_text(label, 14)
    draw_text(
        label,
        int(stack.x + (w - text_width) / 2),
        int(stack.y + h / 2 - 7),
        14,
        Color(100, 100, 100, 150)
    )


def animate(rendered_state, target_state, dt: float = 0.1) -> None:
    for r_stack, t_stack in zip(rendered_state.stacks, target_state.stacks):
        r_stack.cards = t_stack.cards[:]
    rendered_state.loose_cards = target_state.loose_cards[:]
    rendered_state.drag_state = target_state.drag_state
    
    # Interpolate card positions
    for r_card, t_card in zip(rendered_state.cards, target_state.cards):
        r_card.x = r_card.x * (1 - dt) + t_card.x * dt
        r_card.y = r_card.y * (1 - dt) + t_card.y * dt
        r_card.rotation = r_card.rotation * (1 - dt) + t_card.rotation * dt

    selected_card_id = target_state.drag_state.card_id
    if selected_card_id >= 0:
        rendered_state.cards[selected_card_id].x = target_state.cards[selected_card_id].x
        rendered_state.cards[selected_card_id].y = target_state.cards[selected_card_id].y

from copy import deepcopy
state = None  # Global variable to hold current state for drawing
def draw_table(target_state: Table_State) -> None:
    # global state

    global state
    if state is None:
        state = deepcopy(target_state)

    animate(state, target_state)

    """Draw the complete table state."""
    drag = state.drag_state

    # Draw stack placeholders for empty stacks
    for stack in state.stacks:
        if not stack.cards:
            draw_stack_placeholder(stack, "")

    # Draw stacks (excluding dragged card)
    for stack in state.stacks:
        for card_id in stack.cards:
            if card_id == drag.card_id: continue
            card = state.cards[card_id]
            draw_card(card, face_up=stack.face_up)

    # Draw loose cards (excluding dragged card)
    for card_id in state.loose_cards:
        if card_id == drag.card_id: continue
        card = state.cards[card_id]
        draw_card(card, face_up=True)

    # Draw dragged card on top
    if drag.card_id >= 0:
        card = state.cards[drag.card_id]
        draw_card(card, face_up=True)
