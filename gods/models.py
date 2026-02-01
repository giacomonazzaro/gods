from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class Card_Type(Enum):
    WONDER = "wonder"
    EVENT = "event"
    PEOPLE = "people"


class Card_Color(Enum):
    GREEN = "green"
    BLUE = "blue"
    RED = "red"
    YELLOW = "yellow"


@dataclass
class Card:
    name: str
    card_type: Card_Type
    power: int
    color: Card_Color
    effect: str
    destroyed: bool = False
    counters: int = 0  # +1 counters
    owner: Optional[int] = None  # player index who controls this card (for people)

    def effective_power(self) -> int:
        return self.power + self.counters

    def __str__(self) -> str:
        power_str = f"[{self.effective_power()}]" if self.counters else f"[{self.power}]"
        destroyed_str = " (DESTROYED)" if self.destroyed else ""
        return f"{self.name} {power_str} ({self.card_type.value}, {self.color.value}){destroyed_str}"

    def detailed_str(self) -> str:
        effect_text = self.effect.replace("○", str(self.effective_power()))
        return f"{self} - {effect_text}"


@dataclass
class Player:
    name: str
    deck: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    discard: list[Card] = field(default_factory=list)
    wonders: list[Card] = field(default_factory=list)  # wonders in play

    def all_wonders_power(self, color: Optional[Card_Color] = None) -> int:
        total = 0
        for w in self.wonders:
            if color is None or w.color == color:
                total += w.effective_power()
        return total


@dataclass
class Game_State:
    players: list[Player]
    peoples: list[Card]  # people cards in the center
    current_player: int = 0
    game_ending: bool = False  # someone declared end
    ending_player: Optional[int] = None  # who triggered the end
    final_turn: bool = False  # is this the final turn?
    game_over: bool = False
    extra_turns: int = 0  # for Prophecy card
    shared_deck: list[Card] = field(default_factory=list)  # for Stars card

    def active_player(self) -> Player:
        return self.players[self.current_player]

    def opponent(self) -> Player:
        return self.players[1 - self.current_player]

    def switch_turn(self) -> None:
        if self.extra_turns > 0:
            self.extra_turns -= 1
            return

        if self.final_turn:
            self.game_over = True
            return

        self.current_player = 1 - self.current_player

        if self.game_ending and self.current_player != self.ending_player:
            self.final_turn = True
