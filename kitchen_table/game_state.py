from __future__ import annotations
import random
from kitchen_table.models import Card, Stack, Table_State
from kitchen_table.config import tweak


def create_card(id: str, title: str, description: str = "") -> Card:
    return Card(id=id, title=title, description=description)


def create_stack(x: float, y: float, spread_x: float = 0, spread_y: float = 0,
                 face_up: bool = True) -> Stack:
    return Stack(x=x, y=y, spread_x=spread_x, spread_y=spread_y, face_up=face_up)


def add_card_to_stack(card_id: int, stack: Stack, state: Table_State) -> None:
    stack.cards.append(card_id)
    update_card_positions(stack, state)


def remove_card_from_stack(card_id: int, stack: Stack, state: Table_State) -> int | None:
    if card_id in stack.cards:
        stack.cards.remove(card_id)
        update_card_positions(stack, state)
        return card_id
    return None


def update_card_positions(stack: Stack, state: Table_State) -> None:
    """Update x,y positions of all cards in a stack based on spread values."""
    for i, card_id in enumerate(stack.cards):
        card = state.cards[card_id]
        card.x = stack.x + i * stack.spread_x
        card.y = stack.y + i * stack.spread_y


def move_card_to_stack(card_id: int, from_stack: Stack, to_stack: Stack, state: Table_State) -> None:
    remove_card_from_stack(card_id, from_stack, state)
    add_card_to_stack(card_id, to_stack, state)


def find_stack_containing_card(card_id: int, state: Table_State) -> int:
    """Return stack index, or -1 if not found."""
    for i, stack in enumerate(state.stacks):
        if card_id in stack.cards:
            return i
    return -1


def add_loose_card(card_id: int, state: Table_State) -> None:
    """Add a card to the table as a loose card."""
    state.loose_cards.append(card_id)


def remove_loose_card(card_id: int, state: Table_State) -> int | None:
    if card_id in state.loose_cards:
        state.loose_cards.remove(card_id)
        return card_id
    return None


def shuffle_stack(stack: Stack, state: Table_State) -> None:
    """Shuffle the cards in a stack."""
    random.shuffle(stack.cards)
    update_card_positions(stack, state)


def create_sample_cards(state: Table_State) -> list[int]:
    """Create a sample set of cards for testing. Returns list of card indices."""
    card_ids = []
    for i in range(10):
        card = create_card(f"card_{i}", f"Card {i + 1}")
        card_id = len(state.cards)
        state.cards.append(card)
        card_ids.append(card_id)
    return card_ids


def create_example_table_state() -> Table_State:
    """Initialize a new table state with some stacks."""
    state = Table_State()

    # Create a few stacks at different positions
    stack1 = create_stack(100, 300, spread_y=tweak["pile_spread_y"], face_up=False)
    stack2 = create_stack(400, 550, spread_x=tweak["hand_spread_x"])
    stack3 = create_stack(1000, 300, spread_y=tweak["pile_spread_y"])

    state.stacks = [stack1, stack2, stack3]

    # Add sample cards to first stack
    card_ids = create_sample_cards(state)
    random.shuffle(card_ids)
    for card_id in card_ids:
        add_card_to_stack(card_id, stack1, state)

    return state
