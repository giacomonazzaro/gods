from __future__ import annotations
import random
from models import Card, Stack, Drag_State, Table_State
from config import tweak


def create_card(id: str, title: str, description: str = "") -> Card:
    return Card(id=id, title=title, description=description)


def create_stack(x: float, y: float, spread_x: float = 0, spread_y: float = 0,
                 face_up: bool = True) -> Stack:
    return Stack(x=x, y=y, spread_x=spread_x, spread_y=spread_y, face_up=face_up)


def add_card_to_stack(card: Card, stack: Stack) -> None:
    stack.cards.append(card)
    update_card_positions(stack)


def remove_card_from_stack(card: Card, stack: Stack) -> Card | None:
    if card in stack.cards:
        stack.cards.remove(card)
        update_card_positions(stack)
        return card
    return None


def update_card_positions(stack: Stack) -> None:
    """Update x,y positions of all cards in a stack based on spread values."""
    for i, card in enumerate(stack.cards):
        card.x = stack.x + i * stack.spread_x
        card.y = stack.y + i * stack.spread_y


def move_card_to_stack(card: Card, from_stack: Stack, to_stack: Stack) -> None:
    remove_card_from_stack(card, from_stack)
    add_card_to_stack(card, to_stack)


def find_stack_containing_card(card: Card, state: Table_State) -> Stack | None:
    for stack in state.stacks:
        if card in stack.cards:
            return stack
    return None


def add_loose_card(card: Card, state: Table_State) -> None:
    """Add a card to the table as a loose card."""
    state.loose_cards.append(card)


def remove_loose_card(card: Card, state: Table_State) -> Card | None:
    if card in state.loose_cards:
        state.loose_cards.remove(card)
        return card
    return None


def shuffle_stack(stack: Stack) -> None:
    """Shuffle the cards in a stack."""
    random.shuffle(stack.cards)
    update_card_positions(stack)


def create_sample_cards() -> list[Card]:
    """Create a sample set of cards for testing."""
    cards = []
    for i in range(10):
        cards.append(create_card(f"card_{i}", f"Card {i + 1}"))
    return cards


def create_example_table_state() -> Table_State:
    """Initialize a new table state with some stacks."""
    state = Table_State(drag_state=Drag_State())

    # Create a few stacks at different positions
    stack1 = create_stack(100, 300, spread_y=tweak["pile_spread_y"], face_up=False)
    stack2 = create_stack(400, 550, spread_x=tweak["hand_spread_x"])
    stack3 = create_stack(1000, 300, spread_y=tweak["pile_spread_y"])

    state.stacks = [stack1, stack2, stack3]

    # Add sample cards to first stack
    cards = create_sample_cards()
    random.shuffle(cards)
    for card in cards:
        add_card_to_stack(card, stack1)

    return state
