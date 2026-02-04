from __future__ import annotations
from typing import Optional
from pyray import *
from config import tweak
from gods.models import Card as Gods_Card, Player, Game_State
import gods_rendering as gr


class Gods_UI:
    def __init__(self):
        self.messages: list[str] = []
        self.game: Optional[Game_State] = None
        self.ui_state: dict = {
            "messages": self.messages,
            "highlighted_cards": [],
            "selectable_cards": [],
            "pass_hovered": False,
            "end_hovered": False,
        }

    def set_game(self, game: Game_State) -> None:
        self.game = game

    def message(self, text: str) -> None:
        self.messages.append(text)
        if len(self.messages) > 50:
            self.messages.pop(0)

    def _run_modal_loop(self, draw_func, check_func) -> any:
        """Run a modal loop until check_func returns a non-None value."""
        while not window_should_close():
            # Update hover states
            mx, my = get_mouse_x(), get_mouse_y()

            # Draw the game and modal
            begin_drawing()
            gr.draw_game(self.game, self.ui_state)
            draw_func(mx, my)
            end_drawing()

            # Check for selection
            if is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
                result = check_func(mx, my)
                if result is not None:
                    return result

        return None

    def select_card(self, prompt: str, cards: list[Gods_Card]) -> Optional[Gods_Card]:
        """Let player select a card from a list. Shows cards highlighted on the board."""
        if not cards:
            return None

        self.ui_state["highlighted_cards"] = cards
        self.ui_state["selectable_cards"] = cards

        def draw_modal(mx, my):
            # Draw prompt at top
            draw_rectangle(0, 0, tweak["window_width"], 40, Color(0, 0, 0, 200))
            draw_text(prompt, 20, 10, 18, Color(255, 255, 255, 255))
            draw_text("Click a highlighted card to select", 20, 30, 12, Color(200, 200, 200, 255))

        def check_click(mx, my):
            # Check if clicked on any of the selectable cards
            clicked_card = self._find_card_at(mx, my, cards)
            return clicked_card

        result = self._run_modal_loop(draw_modal, check_click)

        self.ui_state["highlighted_cards"] = []
        self.ui_state["selectable_cards"] = []

        return result

    def select_multiple_targets(self, prompt: str, targets: list[tuple[str, any]], max_count: int) -> list:
        """Let player select multiple targets. Returns list of selected values."""
        if not targets:
            return []

        selected = []
        remaining = list(targets)

        while len(selected) < max_count and remaining:
            # Build options including current selection
            options = [(label, val) for label, val in remaining]

            self.ui_state["modal_selected"] = selected
            self.ui_state["modal_allow_skip"] = True
            self.ui_state["modal_hovered"] = -1
            self.ui_state["skip_hovered"] = False

            def draw_modal(mx, my):
                gr.draw_selection_modal(
                    f"{prompt} ({len(selected)}/{max_count} selected)",
                    options,
                    self.ui_state
                )
                # Update hover
                self._update_modal_hover(mx, my, len(options))

            def check_click(mx, my):
                # Check option buttons
                modal_w, modal_h = 600, 400
                modal_x = (tweak["window_width"] - modal_w) / 2
                modal_y = (tweak["window_height"] - modal_h) / 2

                for i in range(len(options)):
                    btn_y = modal_y + 60 + i * 50
                    if modal_x + 20 <= mx <= modal_x + modal_w - 20 and btn_y <= my <= btn_y + 40:
                        return ("select", i)

                # Check skip/done button
                skip_y = modal_y + modal_h - 50
                if modal_x + modal_w - 140 <= mx <= modal_x + modal_w - 20 and skip_y <= my <= skip_y + 35:
                    return ("done", None)

                return None

            result = self._run_modal_loop(draw_modal, check_click)

            if result is None or result[0] == "done":
                break
            elif result[0] == "select":
                idx = result[1]
                _, value = remaining.pop(idx)
                selected.append(value)

        return selected

    def ask_yes_no(self, prompt: str) -> bool:
        """Ask player a yes/no question."""
        self.ui_state["yes_hovered"] = False
        self.ui_state["no_hovered"] = False

        def draw_modal(mx, my):
            # Update hover states
            modal_w, modal_h = 400, 150
            modal_x = (tweak["window_width"] - modal_w) / 2
            modal_y = (tweak["window_height"] - modal_h) / 2

            yes_x, yes_y = modal_x + 50, modal_y + 80
            no_x, no_y = modal_x + 230, modal_y + 80

            self.ui_state["yes_hovered"] = yes_x <= mx <= yes_x + 120 and yes_y <= my <= yes_y + 40
            self.ui_state["no_hovered"] = no_x <= mx <= no_x + 120 and no_y <= my <= no_y + 40

            gr.draw_yes_no_modal(prompt, self.ui_state)

        def check_click(mx, my):
            modal_w, modal_h = 400, 150
            modal_x = (tweak["window_width"] - modal_w) / 2
            modal_y = (tweak["window_height"] - modal_h) / 2

            yes_x, yes_y = modal_x + 50, modal_y + 80
            no_x, no_y = modal_x + 230, modal_y + 80

            if yes_x <= mx <= yes_x + 120 and yes_y <= my <= yes_y + 40:
                return True
            if no_x <= mx <= no_x + 120 and no_y <= my <= no_y + 40:
                return False
            return None

        result = self._run_modal_loop(draw_modal, check_click)
        return result if result is not None else False

    def opponent_select_discard(self, opponent: Player, count: int) -> list[Gods_Card]:
        """Let opponent select cards to discard from their hand."""
        if count <= 0 or not opponent.hand:
            return []

        # For this implementation, opponent selects their own discards
        # In a hidden-hand game, this would need different handling
        cards_to_select = min(count, len(opponent.hand))
        selected = []

        for i in range(cards_to_select):
            remaining = [c for c in opponent.hand if c not in selected]
            self.message(f"{opponent.name} must discard {cards_to_select - i} more card(s)")

            card = self.select_card(
                f"{opponent.name}: Select a card to discard ({i + 1}/{cards_to_select})",
                remaining
            )
            if card:
                selected.append(card)

        return selected

    def _find_card_at(self, mx: float, my: float, cards: list[Gods_Card]) -> Optional[Gods_Card]:
        """Find which card (from the given list) is at the mouse position."""
        if self.game is None:
            return None

        w = tweak["card_width"]
        h = tweak["card_height"]

        # Check player hands
        for player_idx, player in enumerate(self.game.players):
            y_hand = tweak["player1_hand_y"] if player_idx == 0 else tweak["player2_hand_y"]
            for i, card in enumerate(reversed(player.hand)):  # Reverse for z-order
                if card not in cards:
                    continue
                x = tweak["hand_x"] + (len(player.hand) - 1 - i) * tweak["hand_spread_x"]
                if x <= mx <= x + w and y_hand <= my <= y_hand + h:
                    return card

        # Check player wonders
        for player_idx, player in enumerate(self.game.players):
            y_zones = tweak["player1_zones_y"] if player_idx == 0 else tweak["player2_zones_y"]
            for i, wonder in enumerate(reversed(player.wonders)):
                if wonder not in cards:
                    continue
                x = tweak["wonders_x"] + (len(player.wonders) - 1 - i) * tweak["wonders_spread_x"]
                if x <= mx <= x + w and y_zones <= my <= y_zones + h:
                    return wonder

        # Check player discards
        for player_idx, player in enumerate(self.game.players):
            y_zones = tweak["player1_zones_y"] if player_idx == 0 else tweak["player2_zones_y"]
            for card in player.discard:
                if card not in cards:
                    continue
                x = tweak["discard_x"]
                if x <= mx <= x + w and y_zones <= my <= y_zones + h:
                    return card

        # Check peoples
        for i, people in enumerate(self.game.peoples):
            if people not in cards:
                continue
            x = tweak["peoples_x"] + i * tweak["wonders_spread_x"]
            y = tweak["peoples_y"]
            if x <= mx <= x + w and y <= my <= y + h:
                return people

        return None

    def _update_modal_hover(self, mx: float, my: float, num_options: int) -> None:
        """Update hover state for modal options."""
        modal_w, modal_h = 600, 400
        modal_x = (tweak["window_width"] - modal_w) / 2
        modal_y = (tweak["window_height"] - modal_h) / 2

        self.ui_state["modal_hovered"] = -1
        for i in range(num_options):
            btn_y = modal_y + 60 + i * 50
            if modal_x + 20 <= mx <= modal_x + modal_w - 20 and btn_y <= my <= btn_y + 40:
                self.ui_state["modal_hovered"] = i
                break

        # Skip button hover
        skip_y = modal_y + modal_h - 50
        self.ui_state["skip_hovered"] = (
            modal_x + modal_w - 140 <= mx <= modal_x + modal_w - 20 and
            skip_y <= my <= skip_y + 35
        )
