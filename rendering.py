from pyray import *
from models import Card, Stack, Game_State
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


def draw_card(card: Card, face_up: bool = True) -> None:
    """Draw a single card at its position."""
    if not face_up:
        draw_card_back(card.x, card.y)
        return

    w = tweak["card_width"]
    h = tweak["card_height"]
    r = tweak["card_corner_radius"]
    padding = tweak["card_padding"]

    # Card background
    draw_rectangle_rounded(
        Rectangle(card.x, card.y, w, h), r / min(w, h), 8,
        color_from_tuple(tweak["card_background"])
    )

    # Border
    draw_rectangle_rounded_lines_ex(
        Rectangle(card.x, card.y, w, h), r / min(w, h), 8, 2,
        color_from_tuple(tweak["card_border"])
    )

    # Title
    title_size = tweak["title_font_size"]
    draw_text(
        card.title,
        int(card.x + padding),
        int(card.y + padding),
        title_size,
        color_from_tuple(tweak["card_title_color"])
    )

    # Description (with simple word wrapping)
    if card.description:
        desc_size = tweak["description_font_size"]
        desc_y = card.y + padding + title_size + 10
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
                int(card.x + padding),
                int(desc_y + i * (desc_size + 2)),
                desc_size,
                color_from_tuple(tweak["card_description_color"])
            )


def draw_stack(stack: Stack) -> None:
    """Draw all cards in a stack."""
    for card in stack.cards:
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


def draw_game(game_state: Game_State) -> None:
    """Draw the complete game state."""
    # Draw placeholders for empty stacks
    if not game_state.draw_pile.cards:
        draw_stack_placeholder(game_state.draw_pile, "Draw")
    if not game_state.discard_pile.cards:
        draw_stack_placeholder(game_state.discard_pile, "Discard")
    if not game_state.play_area.cards:
        draw_stack_placeholder(game_state.play_area, "Play Area")

    # Draw stacks (excluding dragged card)
    drag = game_state.drag_state

    for stack in [game_state.draw_pile, game_state.discard_pile,
                  game_state.play_area, game_state.hand]:
        for card in stack.cards:
            if card != drag.card:
                draw_card(card, face_up=stack.face_up)

    # Draw dragged card on top
    if drag.card:
        draw_card(drag.card, face_up=True)

    # Draw UI hints
    draw_text("Click draw pile to draw | Drag cards to play | R to end turn",
              10, tweak["window_height"] - 25, 14, Color(150, 150, 150, 255))

    # Draw card counts
    draw_text(f"Draw: {len(game_state.draw_pile.cards)}",
              int(tweak["draw_pile_pos"][0]), int(tweak["draw_pile_pos"][1] - 25),
              14, Color(200, 200, 200, 255))
    draw_text(f"Discard: {len(game_state.discard_pile.cards)}",
              int(tweak["discard_pile_pos"][0]), int(tweak["discard_pile_pos"][1] - 25),
              14, Color(200, 200, 200, 255))
