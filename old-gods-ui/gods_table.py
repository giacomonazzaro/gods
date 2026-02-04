from __future__ import annotations
from typing import Optional
from pyray import *
from config import tweak
from models import Card, Table_State
from gods.models import Card as Gods_Card, Player, Game_State
from rendering import draw_table, draw_card, color_from_tuple


def create_render_card(gods_card: Gods_Card) -> Card:
    """Create a rendering Card linked to a gods Card."""
    return Card(
        id=gods_card.name,
        title=gods_card.name,
        description=gods_card.effect,
        gods_card=gods_card
    )


def build_table_from_game(game: Game_State) -> tuple[Table_State, dict[int, int]]:
    """Build a Table_State from gods Game_State. Returns table and id(card)->index map."""
    table = Table_State()
    card_to_idx: dict[int, int] = {}  # id(gods_card) -> table index

    # Add all cards from both players
    for player in game.players:
        for gods_card in player.deck + player.hand + player.discard + player.wonders:
            if id(gods_card) not in card_to_idx:
                idx = len(table.cards)
                table.cards.append(create_render_card(gods_card))
                card_to_idx[id(gods_card)] = idx

    # Add people cards
    for gods_card in game.peoples:
        if id(gods_card) not in card_to_idx:
            idx = len(table.cards)
            table.cards.append(create_render_card(gods_card))
            card_to_idx[id(gods_card)] = idx

    return table, card_to_idx


def update_card_positions(table: Table_State, game: Game_State, card_to_idx: dict[int, int]) -> None:
    """Update card x,y positions based on game state."""
    for player_idx, player in enumerate(game.players):
        y_hand = tweak["player1_hand_y"] if player_idx == 0 else tweak["player2_hand_y"]
        y_zones = tweak["player1_zones_y"] if player_idx == 0 else tweak["player2_zones_y"]

        # Hand positions
        for i, gods_card in enumerate(player.hand):
            idx = card_to_idx[id(gods_card)]
            table.cards[idx].x = tweak["hand_x"] + i * tweak["hand_spread_x"]
            table.cards[idx].y = y_hand

        # Wonders positions
        for i, gods_card in enumerate(player.wonders):
            idx = card_to_idx[id(gods_card)]
            table.cards[idx].x = tweak["wonders_x"] + i * tweak["wonders_spread_x"]
            table.cards[idx].y = y_zones

        # Discard - show top card
        for i, gods_card in enumerate(player.discard):
            idx = card_to_idx[id(gods_card)]
            table.cards[idx].x = tweak["discard_x"]
            table.cards[idx].y = y_zones

    # Peoples positions
    for i, gods_card in enumerate(game.peoples):
        idx = card_to_idx[id(gods_card)]
        table.cards[idx].x = tweak["peoples_x"] + i * tweak["wonders_spread_x"]
        table.cards[idx].y = tweak["peoples_y"]


class Gods_Table_UI:
    """Graphical UI implementation for gods game."""

    def __init__(self, table: Table_State, game: Game_State, card_to_idx: dict[int, int]):
        self.table = table
        self.game = game
        self.card_to_idx = card_to_idx
        self.messages: list[str] = []
        self.highlighted: list[int] = []

    def message(self, text: str) -> None:
        self.messages.append(text)
        if len(self.messages) > 50:
            self.messages.pop(0)

    def _draw_frame(self, prompt: str = "") -> None:
        """Draw a single frame with current state."""
        update_card_positions(self.table, self.game, self.card_to_idx)

        clear_background(color_from_tuple(tweak["background_color"]))

        # Draw all visible cards
        self._draw_game_state()

        # Draw prompt if any
        if prompt:
            draw_rectangle(0, 0, tweak["window_width"], 50, Color(0, 0, 0, 200))
            draw_text(prompt, 20, 10, 18, Color(255, 255, 255, 255))
            draw_text("Click a highlighted card", 20, 32, 12, Color(200, 200, 200, 255))

        # Draw messages
        msg_y = tweak["ui_y"]
        for i, msg in enumerate(self.messages[-3:]):
            draw_text(msg, 350, int(msg_y + i * 18), 14, Color(200, 200, 200, 255))

        # Turn indicator
        current = self.game.current_player
        indicator_y = tweak["player1_zones_y"] - 30 if current == 0 else tweak["player2_zones_y"] + tweak["card_height"] + 30
        text = f"Player {current + 1}'s Turn"
        w = measure_text(text, 20)
        draw_text(text, int(tweak["window_width"] / 2 - w / 2), int(indicator_y),
                  20, color_from_tuple(tweak["current_player_color"]))

    def _draw_game_state(self) -> None:
        """Draw all cards in the game."""
        w = tweak["card_width"]
        h = tweak["card_height"]

        # Draw decks as backs
        for player_idx, player in enumerate(self.game.players):
            y_zones = tweak["player1_zones_y"] if player_idx == 0 else tweak["player2_zones_y"]
            if player.deck:
                for i in range(min(len(player.deck), 5)):
                    draw_card(Card(id="back", title=""), face_up=False)

        # Draw player hands
        for player in self.game.players:
            for gods_card in player.hand:
                idx = self.card_to_idx[id(gods_card)]
                card = self.table.cards[idx]
                highlighted = idx in self.highlighted
                if highlighted:
                    draw_rectangle_rounded_lines_ex(
                        Rectangle(card.x - 3, card.y - 3, w + 6, h + 6),
                        0.05, 8, 4, color_from_tuple(tweak["highlight_color"])
                    )
                draw_card(card)

        # Draw wonders
        for player in self.game.players:
            for gods_card in player.wonders:
                idx = self.card_to_idx[id(gods_card)]
                card = self.table.cards[idx]
                highlighted = idx in self.highlighted
                if highlighted:
                    draw_rectangle_rounded_lines_ex(
                        Rectangle(card.x - 3, card.y - 3, w + 6, h + 6),
                        0.05, 8, 4, color_from_tuple(tweak["highlight_color"])
                    )
                draw_card(card)

        # Draw discards (top card only)
        for player in self.game.players:
            if player.discard:
                idx = self.card_to_idx[player.discard[-1]]
                draw_card(self.table.cards[idx])

        # Draw peoples
        for gods_card in self.game.peoples:
            idx = self.card_to_idx[id(gods_card)]
            card = self.table.cards[idx]
            highlighted = idx in self.highlighted
            if highlighted:
                draw_rectangle_rounded_lines_ex(
                    Rectangle(card.x - 3, card.y - 3, w + 6, h + 6),
                    0.05, 8, 4, color_from_tuple(tweak["highlight_color"])
                )
            draw_card(card)

    def _find_card_at(self, mx: float, my: float, valid_cards: list[Gods_Card]) -> Optional[Gods_Card]:
        """Find which gods card is at mouse position."""
        w = tweak["card_width"]
        h = tweak["card_height"]

        for gods_card in reversed(valid_cards):
            idx = self.card_to_idx[id(gods_card)]
            card = self.table.cards[idx]
            if card.x <= mx <= card.x + w and card.y <= my <= card.y + h:
                return gods_card
        return None

    def select_card(self, prompt: str, cards: list[Gods_Card]) -> Optional[Gods_Card]:
        """Let player select a card from a list."""
        if not cards:
            return None

        self.highlighted = [self.card_to_idx[id(c)] for c in cards]

        while not window_should_close():
            begin_drawing()
            self._draw_frame(prompt)
            end_drawing()

            if is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
                mx, my = get_mouse_x(), get_mouse_y()
                selected = self._find_card_at(mx, my, cards)
                if selected:
                    self.highlighted = []
                    return selected

        self.highlighted = []
        return None

    def select_multiple_targets(self, prompt: str, targets: list[tuple[str, any]], max_count: int) -> list:
        """Let player select multiple targets via button modal."""
        if not targets:
            return []

        selected = []
        remaining = list(targets)

        while len(selected) < max_count and remaining and not window_should_close():
            # Draw modal with options
            begin_drawing()
            self._draw_frame()

            # Modal overlay
            draw_rectangle(0, 0, tweak["window_width"], tweak["window_height"], Color(0, 0, 0, 180))

            modal_w, modal_h = 500, 350
            modal_x = (tweak["window_width"] - modal_w) / 2
            modal_y = (tweak["window_height"] - modal_h) / 2

            draw_rectangle_rounded(Rectangle(modal_x, modal_y, modal_w, modal_h), 0.05, 8, Color(50, 50, 60, 255))
            draw_text(f"{prompt} ({len(selected)}/{max_count})", int(modal_x + 20), int(modal_y + 20), 16, Color(255, 255, 255, 255))

            mx, my = get_mouse_x(), get_mouse_y()
            clicked_idx = -1

            for i, (label, _) in enumerate(remaining[:6]):
                btn_y = modal_y + 60 + i * 45
                hovered = modal_x + 20 <= mx <= modal_x + modal_w - 20 and btn_y <= my <= btn_y + 35
                color = tweak["button_hover_color"] if hovered else tweak["button_color"]
                draw_rectangle_rounded(Rectangle(modal_x + 20, btn_y, modal_w - 40, 35), 0.3, 8, color_from_tuple(color))
                draw_text(label, int(modal_x + 30), int(btn_y + 8), 14, Color(255, 255, 255, 255))

                if hovered and is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
                    clicked_idx = i

            # Done button
            done_y = modal_y + modal_h - 50
            done_hovered = modal_x + modal_w - 100 <= mx <= modal_x + modal_w - 20 and done_y <= my <= done_y + 35
            done_color = tweak["button_hover_color"] if done_hovered else tweak["button_color"]
            draw_rectangle_rounded(Rectangle(modal_x + modal_w - 100, done_y, 80, 35), 0.3, 8, color_from_tuple(done_color))
            draw_text("Done", int(modal_x + modal_w - 80), int(done_y + 8), 14, Color(255, 255, 255, 255))

            if done_hovered and is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
                break

            end_drawing()

            if clicked_idx >= 0:
                _, value = remaining.pop(clicked_idx)
                selected.append(value)

        return selected

    def ask_yes_no(self, prompt: str) -> bool:
        """Ask yes/no question."""
        while not window_should_close():
            begin_drawing()
            self._draw_frame()

            draw_rectangle(0, 0, tweak["window_width"], tweak["window_height"], Color(0, 0, 0, 180))

            modal_w, modal_h = 400, 150
            modal_x = (tweak["window_width"] - modal_w) / 2
            modal_y = (tweak["window_height"] - modal_h) / 2

            draw_rectangle_rounded(Rectangle(modal_x, modal_y, modal_w, modal_h), 0.05, 8, Color(50, 50, 60, 255))
            draw_text(prompt, int(modal_x + 20), int(modal_y + 20), 16, Color(255, 255, 255, 255))

            mx, my = get_mouse_x(), get_mouse_y()

            yes_x, yes_y = modal_x + 50, modal_y + 80
            no_x, no_y = modal_x + 230, modal_y + 80

            yes_hovered = yes_x <= mx <= yes_x + 120 and yes_y <= my <= yes_y + 40
            no_hovered = no_x <= mx <= no_x + 120 and no_y <= my <= no_y + 40

            yes_color = tweak["button_hover_color"] if yes_hovered else tweak["button_color"]
            no_color = tweak["button_hover_color"] if no_hovered else tweak["button_color"]

            draw_rectangle_rounded(Rectangle(yes_x, yes_y, 120, 40), 0.3, 8, color_from_tuple(yes_color))
            draw_rectangle_rounded(Rectangle(no_x, no_y, 120, 40), 0.3, 8, color_from_tuple(no_color))
            draw_text("Yes", int(yes_x + 45), int(yes_y + 10), 16, Color(255, 255, 255, 255))
            draw_text("No", int(no_x + 50), int(no_y + 10), 16, Color(255, 255, 255, 255))

            end_drawing()

            if is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
                if yes_hovered:
                    return True
                if no_hovered:
                    return False

        return False

    def opponent_select_discard(self, opponent: Player, count: int) -> list[Gods_Card]:
        """Let opponent select cards to discard."""
        if count <= 0 or not opponent.hand:
            return []

        selected = []
        for i in range(min(count, len(opponent.hand))):
            remaining = [c for c in opponent.hand if c not in selected]
            self.message(f"{opponent.name} must discard {count - i} card(s)")
            card = self.select_card(f"{opponent.name}: Select card to discard ({i+1}/{count})", remaining)
            if card:
                selected.append(card)
        return selected
