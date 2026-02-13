from __future__ import annotations
import threading
from dataclasses import dataclass, field
from typing import Callable

from gods.models import Game_State, Choice, Card, Card_Id
import kitchen_table.models as kt
from kitchen_table.config import tweak


@dataclass
class Agent_Graphical:
    """Graphical agent that displays choices through the kitchen_table UI."""
    table_state: kt.Table_State
    card_mapping: dict = field(default_factory=dict)  # gods card name -> kt card index

    # Threading synchronization
    selection_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    # Choice state
    pending_choice: Choice | None = None
    choice_type: str = ""  # "main", "card", "button"
    selected_option: int = -1
    option_to_card: dict = field(default_factory=dict)  # option index -> kt card index

    # Message log
    messages: list[str] = field(default_factory=list)

    def build_card_mapping(self, gods_state: Game_State) -> None:
        """Build mapping from gods card names to kitchen_table card indices."""
        self.card_mapping = {}
        for i, kt_card in enumerate(self.table_state.cards):
            self.card_mapping[kt_card.id] = i

    def message(self, msg: str) -> None:
        """Display a game message."""
        with self.lock:
            self.messages.append(msg)
            self.table_state.message = msg
            # Keep only last 10 messages
            if len(self.messages) > 10:
                self.messages.pop(0)

    def choose_action(self, state: Game_State, choice: Choice) -> int:
        """Handle a game choice by showing options in the UI and waiting for selection."""
        with self.lock:
            self.pending_choice = choice
            self.selected_option = -1
            self.selection_event.clear()

            # Determine choice type and setup UI
            self._setup_choice_ui(state, choice)

        # Block until user makes a selection
        self.selection_event.wait()

        with self.lock:
            selected = self.selected_option
            self._clear_choice_ui()
            self.pending_choice = None

        # Resolve the choice
        choice.resolve(state, choice, selected)
        return selected

    def _setup_choice_ui(self, state: Game_State, choice: Choice) -> None:
        """Setup the UI elements for the current choice."""
        options = choice.option_descriptions

        # Check if this is a card selection choice (options are card names)
        card_options = self._find_card_options(state, choice)

        if card_options:
            # Card selection - highlight selectable cards
            self.choice_type = "card"
            self.option_to_card = {}
            selectable = []

            for opt_idx, (card_name, kt_idx) in card_options.items():
                self.option_to_card[kt_idx] = opt_idx
                selectable.append(kt_idx)

            self.table_state.selectable_cards = selectable
            self.table_state.buttons = []
            self.table_state.message = f"Select a card ({len(selectable)} options)"
        else:
            # Button-based choice (main actions, etc.)
            self.choice_type = "button"
            self.option_to_card = {}
            self.table_state.selectable_cards = []

            # Create buttons for each option
            button_width = tweak["button_width"]
            button_height = tweak["button_height"]
            spacing = 20
            total_width = len(options) * button_width + (len(options) - 1) * spacing
            start_x = (tweak["window_width"] - total_width) / 2
            y = tweak["window_height"] - 80

            buttons = []
            for i, label in enumerate(options):
                btn = kt.Button(
                    label=label[:15],  # Truncate long labels
                    x=start_x + i * (button_width + spacing),
                    y=y,
                    width=button_width,
                    height=button_height
                )
                buttons.append(btn)

            self.table_state.buttons = buttons
            player = state.active_player()
            self.table_state.message = f"{player.name}'s turn"

    def _find_card_options(self, state: Game_State, choice: Choice) -> dict:
        """Check if choice options correspond to cards and return mapping."""
        result = {}
        player = state.players[choice.player_index]

        for i, desc in enumerate(choice.option_descriptions):
            # Check if this option is a card name in player's hand
            for card in player.hand:
                if card.name in desc and card.name in self.card_mapping:
                    kt_idx = self.card_mapping[card.name]
                    result[i] = (card.name, kt_idx)
                    break

            # Also check wonders and discard for certain effects
            if i not in result:
                for card in player.wonders:
                    if card.name in desc and card.name in self.card_mapping:
                        kt_idx = self.card_mapping[card.name]
                        result[i] = (card.name, kt_idx)
                        break

            if i not in result:
                for card in player.discard:
                    if card.name in desc and card.name in self.card_mapping:
                        kt_idx = self.card_mapping[card.name]
                        result[i] = (card.name, kt_idx)
                        break

            # Check people cards
            if i not in result:
                for card in state.peoples:
                    if card.name in desc and card.name in self.card_mapping:
                        kt_idx = self.card_mapping[card.name]
                        result[i] = (card.name, kt_idx)
                        break

            # Check opponent's wonders for certain effects
            if i not in result:
                opponent = state.players[1 - choice.player_index]
                for card in opponent.wonders:
                    if card.name in desc and card.name in self.card_mapping:
                        kt_idx = self.card_mapping[card.name]
                        result[i] = (card.name, kt_idx)
                        break

        # Only return if ALL options are cards (or most of them)
        # This helps distinguish pure card choices from mixed choices
        if len(result) == len(choice.option_descriptions):
            return result
        elif len(result) > 0 and len(result) >= len(choice.option_descriptions) - 1:
            # Allow one non-card option (like "Pass" or "Cancel")
            return result

        return {}

    def _clear_choice_ui(self) -> None:
        """Clear UI elements after choice is made."""
        self.table_state.selectable_cards = []
        self.table_state.buttons = []
        self.table_state.selected_card = -1
        self.table_state.selected_button = -1
        self.table_state.message = ""

    def handle_selection(self) -> bool:
        """Check if user made a selection and signal the game thread.
        Returns True if a selection was made.
        Called from the render loop.
        """
        with self.lock:
            if self.pending_choice is None:
                return False

            if self.choice_type == "card":
                if self.table_state.selected_card >= 0:
                    kt_idx = self.table_state.selected_card
                    if kt_idx in self.option_to_card:
                        self.selected_option = self.option_to_card[kt_idx]
                        self.table_state.selected_card = -1
                        self.selection_event.set()
                        return True

            elif self.choice_type == "button":
                if self.table_state.selected_button >= 0:
                    self.selected_option = self.table_state.selected_button
                    self.table_state.selected_button = -1
                    self.selection_event.set()
                    return True

        return False
