from __future__ import annotations
from pyray import *
from config import tweak
from gods.models import Card as Gods_Card, Card_Type, Card_Color, Player, Game_State
from models import Card, Stack, Table_State


def color_from_tuple(c: tuple) -> Color:
    return Color(c[0], c[1], c[2], c[3])


def get_card_background_color(card: Gods_Card) -> tuple:
    color_map = {
        Card_Color.GREEN: tweak["color_green"],
        Card_Color.BLUE: tweak["color_blue"],
        Card_Color.RED: tweak["color_red"],
        Card_Color.YELLOW: tweak["color_yellow"],
    }
    return color_map.get(card.color, tweak["card_background"])


def draw_gods_card(x: float, y: float, gods_card: Gods_Card, highlighted: bool = False, selectable: bool = True) -> None:
    w = tweak["card_width"]
    h = tweak["card_height"]
    r = tweak["card_corner_radius"]
    padding = tweak["card_padding"]

    # Handle destroyed cards (rotated 90 degrees)
    if gods_card.destroyed:
        cx = x + w / 2
        cy = y + h / 2
        rl_push_matrix()
        rl_translatef(cx, cy, 0)
        rl_rotatef(90, 0, 0, 1)
        rl_translatef(-cx, -cy, 0)

    # Card background with type color
    bg_color = get_card_background_color(gods_card)
    if not selectable:
        bg_color = (bg_color[0] // 2, bg_color[1] // 2, bg_color[2] // 2, bg_color[3])
    draw_rectangle_rounded(
        Rectangle(x, y, w, h), r / min(w, h), 8,
        color_from_tuple(bg_color)
    )

    # Highlight border if selected
    if highlighted:
        draw_rectangle_rounded_lines_ex(
            Rectangle(x - 3, y - 3, w + 6, h + 6), r / min(w, h), 8, 4,
            color_from_tuple(tweak["highlight_color"])
        )

    # Regular border
    draw_rectangle_rounded_lines_ex(
        Rectangle(x, y, w, h), r / min(w, h), 8, 2,
        color_from_tuple(tweak["card_border"])
    )

    # Power circle in top-left
    power = gods_card.effective_power()
    power_radius = 16
    power_x = x + power_radius + 4
    power_y = y + power_radius + 4
    draw_circle(int(power_x), int(power_y), power_radius, Color(50, 50, 50, 255))
    power_text = str(power)
    power_width = measure_text(power_text, tweak["power_font_size"])
    draw_text(
        power_text,
        int(power_x - power_width / 2),
        int(power_y - tweak["power_font_size"] / 2),
        tweak["power_font_size"],
        Color(255, 255, 255, 255)
    )

    # Counters indicator (if any)
    if gods_card.counters > 0:
        counter_text = f"+{gods_card.counters}"
        draw_text(
            counter_text,
            int(x + w - 30),
            int(y + 8),
            14,
            Color(0, 150, 0, 255)
        )

    # Card name
    name_y = y + 40
    draw_text(
        gods_card.name,
        int(x + padding),
        int(name_y),
        tweak["title_font_size"],
        color_from_tuple(tweak["card_title_color"])
    )

    # Card type
    type_y = name_y + tweak["title_font_size"] + 2
    type_text = gods_card.card_type.value.upper()
    draw_text(
        type_text,
        int(x + padding),
        int(type_y),
        10,
        Color(100, 100, 100, 255)
    )

    # Effect text (with word wrapping)
    if gods_card.effect:
        effect_y = type_y + 14
        max_width = w - 2 * padding
        effect_text = gods_card.effect.replace("○", str(power))

        words = effect_text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            text_width = measure_text(test_line, tweak["description_font_size"])
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for i, line in enumerate(lines[:4]):  # Limit to 4 lines
            draw_text(
                line,
                int(x + padding),
                int(effect_y + i * (tweak["description_font_size"] + 2)),
                tweak["description_font_size"],
                color_from_tuple(tweak["card_description_color"])
            )

    # Owner indicator for peoples
    if gods_card.card_type == Card_Type.PEOPLE and gods_card.owner is not None:
        owner_color = Color(100, 200, 100, 255) if gods_card.owner == 0 else Color(200, 100, 100, 255)
        draw_rectangle(int(x + w - 20), int(y + h - 20), 15, 15, owner_color)

    if gods_card.destroyed:
        rl_pop_matrix()


def draw_card_back(x: float, y: float) -> None:
    w = tweak["card_width"]
    h = tweak["card_height"]
    r = tweak["card_corner_radius"]

    draw_rectangle_rounded(
        Rectangle(x, y, w, h), r / min(w, h), 8,
        color_from_tuple(tweak["card_back"])
    )
    margin = 10
    draw_rectangle_rounded(
        Rectangle(x + margin, y + margin, w - 2*margin, h - 2*margin),
        r / min(w, h), 8,
        color_from_tuple(tweak["card_back_pattern"])
    )
    draw_rectangle_rounded_lines_ex(
        Rectangle(x, y, w, h), r / min(w, h), 8, 2,
        color_from_tuple(tweak["card_border"])
    )


def draw_deck_pile(x: float, y: float, count: int, label: str) -> None:
    w = tweak["card_width"]
    h = tweak["card_height"]

    if count > 0:
        # Draw stacked backs
        for i in range(min(count, 5)):
            draw_card_back(x + i * 2, y - i * 2)
        # Count label
        count_text = str(count)
        draw_text(count_text, int(x + w / 2 - 10), int(y + h / 2 - 10), 20, Color(255, 255, 255, 255))
    else:
        # Empty placeholder
        draw_rectangle_rounded_lines_ex(
            Rectangle(x, y, w, h),
            tweak["card_corner_radius"] / min(w, h), 8, 1,
            Color(100, 100, 100, 100)
        )

    # Label below
    label_width = measure_text(label, 12)
    draw_text(label, int(x + (w - label_width) / 2), int(y + h + 5), 12, Color(150, 150, 150, 255))


def draw_button(x: float, y: float, w: float, h: float, text: str, hovered: bool = False, enabled: bool = True) -> None:
    color = tweak["button_hover_color"] if hovered else tweak["button_color"]
    if not enabled:
        color = (80, 80, 80, 255)
    draw_rectangle_rounded(
        Rectangle(x, y, w, h), 0.3, 8,
        color_from_tuple(color)
    )
    text_width = measure_text(text, 16)
    draw_text(
        text,
        int(x + (w - text_width) / 2),
        int(y + (h - 16) / 2),
        16,
        color_from_tuple(tweak["button_text_color"])
    )


def draw_player_zone(game: Game_State, player_idx: int, y_hand: float, y_zones: float,
                     highlighted_cards: list[Gods_Card] = None, selectable_cards: list[Gods_Card] = None) -> None:
    if highlighted_cards is None:
        highlighted_cards = []
    if selectable_cards is None:
        selectable_cards = []

    player = game.players[player_idx]
    w = tweak["card_width"]
    spread = tweak["hand_spread_x"]

    # Hand
    hand_x = tweak["hand_x"]
    for i, card in enumerate(player.hand):
        x = hand_x + i * spread
        is_highlighted = card in highlighted_cards
        is_selectable = len(selectable_cards) == 0 or card in selectable_cards
        draw_gods_card(x, y_hand, card, highlighted=is_highlighted, selectable=is_selectable)

    # Deck
    draw_deck_pile(tweak["deck_x"], y_zones, len(player.deck), "Deck")

    # Discard
    if player.discard:
        draw_gods_card(tweak["discard_x"], y_zones, player.discard[-1])
        if len(player.discard) > 1:
            count_text = str(len(player.discard))
            draw_text(count_text, int(tweak["discard_x"] + w - 20), int(y_zones + 5), 14, Color(100, 100, 100, 255))
    else:
        draw_rectangle_rounded_lines_ex(
            Rectangle(tweak["discard_x"], y_zones, w, tweak["card_height"]),
            tweak["card_corner_radius"] / min(w, tweak["card_height"]), 8, 1,
            Color(100, 100, 100, 100)
        )
    label_width = measure_text("Discard", 12)
    draw_text("Discard", int(tweak["discard_x"] + (w - label_width) / 2),
              int(y_zones + tweak["card_height"] + 5), 12, Color(150, 150, 150, 255))

    # Wonders in play
    wonders_x = tweak["wonders_x"]
    for i, wonder in enumerate(player.wonders):
        x = wonders_x + i * tweak["wonders_spread_x"]
        is_highlighted = wonder in highlighted_cards
        is_selectable = len(selectable_cards) == 0 or wonder in selectable_cards
        draw_gods_card(x, y_zones, wonder, highlighted=is_highlighted, selectable=is_selectable)


def draw_peoples(game: Game_State, highlighted_cards: list[Gods_Card] = None,
                 selectable_cards: list[Gods_Card] = None) -> None:
    if highlighted_cards is None:
        highlighted_cards = []
    if selectable_cards is None:
        selectable_cards = []

    y = tweak["peoples_y"]
    x_start = tweak["peoples_x"]
    spread = tweak["wonders_spread_x"]

    for i, people in enumerate(game.peoples):
        x = x_start + i * spread
        is_highlighted = people in highlighted_cards
        is_selectable = len(selectable_cards) == 0 or people in selectable_cards
        draw_gods_card(x, y, people, highlighted=is_highlighted, selectable=is_selectable)


def animate(rendered_state, state, dt: float = 0.1) -> None:
    for r_stack, t_stack in zip(rendered_state.stacks, state.stacks):
        r_stack.cards = t_stack.cards[:]
    rendered_state.loose_cards = state.loose_cards[:]
    rendered_state.drag_state = state.drag_state
    animate(rendered_state, state)
    
    # Interpolate card positions
    for r_card, t_card in zip(rendered_state.cards, state.cards):
        r_card.x = r_card.x * (1 - dt) + t_card.x * dt
        r_card.y = r_card.y * (1 - dt) + t_card.y * dt
        r_card.rotation = r_card.rotation * (1 - dt) + t_card.rotation * dt

    rendered_state.cards[state.drag_state.card_id].x = state.cards[state.drag_state.card_id].x
    rendered_state.cards[state.drag_state.card_id].y = state.cards[state.drag_state.card_id].y


rendered_state = None
def draw_game(game: Game_State, ui_state: dict) -> None:
    global rendered_state
    if rendered_state is None:
        from copy import deepcopy
        rendered_state = deepcopy(game)
        
    animate(rendered_state, game)

    # Clear background
    clear_background(color_from_tuple(tweak["background_color"]))

    highlighted = ui_state.get("highlighted_cards", [])
    selectable = ui_state.get("selectable_cards", [])

    # Player 2 zone (top)
    draw_player_zone(game, 1, tweak["player2_hand_y"], tweak["player2_zones_y"], highlighted, selectable)

    # Peoples (center)
    draw_peoples(game, highlighted, selectable)

    # Player 1 zone (bottom)
    draw_player_zone(game, 0, tweak["player1_hand_y"], tweak["player1_zones_y"], highlighted, selectable)

    # Current player indicator
    current_player = game.current_player
    indicator_y = tweak["player1_zones_y"] - 30 if current_player == 0 else tweak["player2_zones_y"] + tweak["card_height"] + 30
    player_text = f"Player {current_player + 1}'s Turn"
    text_width = measure_text(player_text, 20)
    draw_text(player_text, int(tweak["window_width"] / 2 - text_width / 2), int(indicator_y),
              20, color_from_tuple(tweak["current_player_color"]))

    # Action buttons
    button_y = tweak["ui_y"]
    pass_hovered = ui_state.get("pass_hovered", False)
    end_hovered = ui_state.get("end_hovered", False)
    can_end = not game.game_ending

    draw_button(50, button_y, tweak["button_width"], tweak["button_height"], "Pass", pass_hovered)
    draw_button(190, button_y, tweak["button_width"], tweak["button_height"], "End Game", end_hovered, can_end)

    # Messages
    messages = ui_state.get("messages", [])
    msg_y = button_y
    for i, msg in enumerate(messages[-3:]):  # Show last 3 messages
        draw_text(msg, 350, int(msg_y + i * 18), 14, Color(200, 200, 200, 255))

    # Game state indicators
    if game.game_ending:
        status = "FINAL TURN" if game.final_turn else "GAME ENDING"
        draw_text(status, int(tweak["window_width"] - 150), int(button_y), 16, Color(255, 100, 100, 255))

    if game.game_over:
        draw_game_over_overlay(game, ui_state)


def draw_game_over_overlay(game: Game_State, ui_state: dict) -> None:
    # Dim background
    draw_rectangle(0, 0, tweak["window_width"], tweak["window_height"], Color(0, 0, 0, 200))

    scores = ui_state.get("scores", (0, 0))
    winner = ui_state.get("winner", None)

    # Title
    title = "GAME OVER"
    title_width = measure_text(title, 40)
    draw_text(title, int(tweak["window_width"] / 2 - title_width / 2), 300, 40, Color(255, 255, 255, 255))

    # Scores
    score_text = f"Player 1: {scores[0]}  -  Player 2: {scores[1]}"
    score_width = measure_text(score_text, 24)
    draw_text(score_text, int(tweak["window_width"] / 2 - score_width / 2), 360, 24, Color(200, 200, 200, 255))

    # Winner
    if winner is not None:
        winner_text = f"Player {winner + 1} Wins!"
        winner_width = measure_text(winner_text, 32)
        draw_text(winner_text, int(tweak["window_width"] / 2 - winner_width / 2), 420, 32, Color(100, 255, 100, 255))


def draw_selection_modal(prompt: str, options: list[tuple[str, any]], ui_state: dict) -> None:
    # Dim background
    draw_rectangle(0, 0, tweak["window_width"], tweak["window_height"],
                   color_from_tuple(tweak["modal_overlay"]))

    # Modal box
    modal_w = 600
    modal_h = 400
    modal_x = (tweak["window_width"] - modal_w) / 2
    modal_y = (tweak["window_height"] - modal_h) / 2

    draw_rectangle_rounded(
        Rectangle(modal_x, modal_y, modal_w, modal_h), 0.05, 8,
        Color(50, 50, 60, 255)
    )

    # Prompt
    draw_text(prompt, int(modal_x + 20), int(modal_y + 20), 18, Color(255, 255, 255, 255))

    # Options as buttons
    button_y = modal_y + 60
    hovered_idx = ui_state.get("modal_hovered", -1)

    for i, (label, _) in enumerate(options):
        is_hovered = i == hovered_idx
        draw_button(modal_x + 20, button_y + i * 50, modal_w - 40, 40, label, is_hovered)

    # Cancel/Skip button
    selected = ui_state.get("modal_selected", [])
    if ui_state.get("modal_allow_skip", False):
        skip_y = modal_y + modal_h - 50
        skip_hovered = ui_state.get("skip_hovered", False)
        draw_button(modal_x + modal_w - 140, skip_y, 120, 35, "Done", skip_hovered)


def draw_yes_no_modal(prompt: str, ui_state: dict) -> None:
    # Dim background
    draw_rectangle(0, 0, tweak["window_width"], tweak["window_height"],
                   color_from_tuple(tweak["modal_overlay"]))

    # Modal box
    modal_w = 400
    modal_h = 150
    modal_x = (tweak["window_width"] - modal_w) / 2
    modal_y = (tweak["window_height"] - modal_h) / 2

    draw_rectangle_rounded(
        Rectangle(modal_x, modal_y, modal_w, modal_h), 0.05, 8,
        Color(50, 50, 60, 255)
    )

    # Prompt
    draw_text(prompt, int(modal_x + 20), int(modal_y + 20), 16, Color(255, 255, 255, 255))

    # Yes/No buttons
    yes_hovered = ui_state.get("yes_hovered", False)
    no_hovered = ui_state.get("no_hovered", False)

    draw_button(modal_x + 50, modal_y + 80, 120, 40, "Yes", yes_hovered)
    draw_button(modal_x + 230, modal_y + 80, 120, 40, "No", no_hovered)
