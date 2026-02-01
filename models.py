from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Card:
    id: str
    title: str
    description: str = ""
    image_path: str | None = None
    x: float = 0.0
    y: float = 0.0
    tapped: bool = False  # Whether the card is rotated (e.g., for certain game mechanics)

@dataclass
class Stack:
    x: float
    y: float
    cards: list[Card] = field(default_factory=list)
    spread_x: float = 0.0  # Horizontal offset between cards
    spread_y: float = 0.0  # Vertical offset between cards
    face_up: bool = True   # Whether cards are visible


@dataclass
class Drag_State:
    card: Card | None = None
    source_stack: Stack | None = None
    offset_x: float = 0.0
    offset_y: float = 0.0


@dataclass
class Table_State:
    stacks: list[Stack] = field(default_factory=list)
    loose_cards: list[Card] = field(default_factory=list)  # Cards not in any stack
    drag_state: Drag_State = field(default_factory=Drag_State)
