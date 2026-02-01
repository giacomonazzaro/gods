from __future__ import annotations
import json
import random
from typing import Callable, Optional
from models import Card, Card_Type, Card_Color, Game_State, Player


def load_cards_from_json(filepath: str) -> list[dict]:
    with open(filepath, 'r') as f:
        return json.load(f)


def create_card(data: dict, default_power: int = 3) -> Card:
    card_type = Card_Type(data["type"])
    color = Card_Color(data["color"])
    # Use the power from data if it's a people card (they have fixed power), otherwise use default
    power = data["power"] if card_type == Card_Type.PEOPLE else default_power
    return Card(
        name=data["name"],
        card_type=card_type,
        power=power,
        color=color,
        effect=data["effect"]
    )


def get_all_cards(default_power: int = 3) -> list[Card]:
    import os
    filepath = os.path.join(os.path.dirname(__file__), "cards.json")
    data = load_cards_from_json(filepath)
    return [create_card(d, default_power) for d in data]


def get_people_cards(default_power: int = 3) -> list[Card]:
    return [c for c in get_all_cards(default_power) if c.card_type == Card_Type.PEOPLE]


def get_playable_cards(default_power: int = 3) -> list[Card]:
    return [c for c in get_all_cards(default_power) if c.card_type != Card_Type.PEOPLE]


# Effect implementations
# Each effect function takes (game_state, card, ui_callback) and returns True if successful

def effect_rivers(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: handled in people condition checking
    return True


def effect_meteorite(game: Game_State, card: Card, ui: any) -> bool:
    # Destroy all opponent peoples with power ○ or less
    power = card.effective_power()
    opponent = game.opponent()
    for people in game.peoples:
        if people.owner == (1 - game.current_player):
            if people.effective_power() <= power and not is_indestructible(game, people, 1 - game.current_player):
                people.destroyed = True
                ui.message(f"{people.name} was destroyed!")
    return True


def effect_earthquake(game: Game_State, card: Card, ui: any) -> bool:
    # Destroy all peoples with power ○ or less
    power = card.effective_power()
    for people in game.peoples:
        if people.effective_power() <= power:
            owner_idx = people.owner
            if owner_idx is None or not is_indestructible(game, people, owner_idx):
                people.destroyed = True
                ui.message(f"{people.name} was destroyed!")
    return True


def effect_eruption(game: Game_State, card: Card, ui: any) -> bool:
    # Shuffle up to ○ blue wonders into their owners' decks
    power = card.effective_power()
    targets = []
    for p in game.players:
        for w in p.wonders:
            if w.color == Card_Color.BLUE:
                targets.append((p, w))

    if not targets:
        ui.message("No blue wonders to shuffle.")
        return True

    count = min(power, len(targets))
    selected = ui.select_multiple_targets(
        f"Select up to {count} blue wonders to shuffle back:",
        [(f"{p.name}'s {w.name}", (p, w)) for p, w in targets],
        max_count=count
    )

    for player, wonder in selected:
        player.wonders.remove(wonder)
        wonder.counters = 0
        player.deck.append(wonder)
        random.shuffle(player.deck)
        ui.message(f"{wonder.name} shuffled into {player.name}'s deck.")
    return True


def effect_miracle(game: Game_State, card: Card, ui: any) -> bool:
    # Play another event, it gets +○
    power = card.effective_power()
    player = game.active_player()
    events = [c for c in player.hand if c.card_type == Card_Type.EVENT]

    if not events:
        ui.message("No events in hand to play with Miracle.")
        return True

    selected = ui.select_card("Select an event to play with +{} power:".format(power), events)
    if selected:
        selected.counters += power
        player.hand.remove(selected)
        execute_card_effect(game, selected, ui)
        selected.counters -= power
        player.discard.append(selected)
    return True


def effect_flashback(game: Game_State, card: Card, ui: any) -> bool:
    # Return ○ event cards from your discard pile to your hand
    power = card.effective_power()
    player = game.active_player()
    events = [c for c in player.discard if c.card_type == Card_Type.EVENT]

    if not events:
        ui.message("No events in discard pile.")
        return True

    count = min(power, len(events))
    selected = ui.select_multiple_targets(
        f"Select up to {count} events to return to hand:",
        [(c.name, c) for c in events],
        max_count=count
    )

    for event in selected:
        player.discard.remove(event)
        player.hand.append(event)
        ui.message(f"{event.name} returned to hand.")
    return True


def effect_prophecy(game: Game_State, card: Card, ui: any) -> bool:
    # Take ○ extra turns
    game.extra_turns += card.effective_power()
    ui.message(f"You will take {card.effective_power()} extra turn(s)!")
    return True


def effect_time_warp(game: Game_State, card: Card, ui: any) -> bool:
    # Return up to ○ wonders from play to their owners' hands
    power = card.effective_power()
    targets = []
    for p in game.players:
        for w in p.wonders:
            targets.append((p, w))

    if not targets:
        ui.message("No wonders in play.")
        return True

    count = min(power, len(targets))
    selected = ui.select_multiple_targets(
        f"Select up to {count} wonders to return to hand:",
        [(f"{p.name}'s {w.name}", (p, w)) for p, w in targets],
        max_count=count
    )

    for player, wonder in selected:
        player.wonders.remove(wonder)
        wonder.counters = 0
        player.hand.append(wonder)
        ui.message(f"{wonder.name} returned to {player.name}'s hand.")
    return True


def effect_aurora(game: Game_State, card: Card, ui: any) -> bool:
    # Draw ○ cards
    power = card.effective_power()
    player = game.active_player()
    for _ in range(power):
        draw_card(game, player, ui)
    return True


def effect_darkness(game: Game_State, card: Card, ui: any) -> bool:
    # The opponent discards ○ cards from their hand
    power = card.effective_power()
    opponent = game.opponent()
    count = min(power, len(opponent.hand))

    if count == 0:
        ui.message("Opponent has no cards to discard.")
        return True

    selected = ui.opponent_select_discard(opponent, count)
    for c in selected:
        opponent.hand.remove(c)
        opponent.discard.append(c)
        ui.message(f"{opponent.name} discarded {c.name}.")
    return True


def effect_spring(game: Game_State, card: Card, ui: any) -> bool:
    # Add ○ +1 counters on a people
    power = card.effective_power()
    if not game.peoples:
        ui.message("No people cards to add counters to.")
        return True

    selected = ui.select_card("Select a people to add {} counters:".format(power), game.peoples)
    if selected:
        selected.counters += power
        ui.message(f"Added {power} +1 counters to {selected.name}.")
    return True


def effect_regrowth(game: Game_State, card: Card, ui: any) -> bool:
    # Restore any number of peoples with power ○ or less
    power = card.effective_power()
    destroyed = [p for p in game.peoples if p.destroyed and p.effective_power() <= power]

    if not destroyed:
        ui.message("No destroyed peoples to restore.")
        return True

    selected = ui.select_multiple_targets(
        "Select peoples to restore:",
        [(p.name, p) for p in destroyed],
        max_count=len(destroyed)
    )

    for people in selected:
        people.destroyed = False
        ui.message(f"{people.name} was restored!")
    return True


def effect_wisdom(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: Your other blue wonders get +○
    return True


def effect_knowledge(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: When you pass, you may play a card with power ○ or less
    return True


def effect_sky(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: Opponent events get ○ down to a minimum of 1 power
    return True


def effect_deserts(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: You can score destroyed peoples with power ○ or less
    return True


def effect_forests(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: When you pass, you may restore a people with power ○ or less
    return True


def effect_mountains(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: Your peoples with power ○ or less are indestructible
    return True


def effect_flood(game: Game_State, card: Card, ui: any) -> bool:
    # Destroy all unclaimed peoples with power ○ or less
    power = card.effective_power()
    for people in game.peoples:
        if people.owner is None and people.effective_power() <= power:
            people.destroyed = True
            ui.message(f"{people.name} was destroyed!")
    return True


def effect_animals(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: This is worth ○ points at the end of the game
    return True


def effect_war(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: When you pass, you may destroy a people with power ○ or less
    return True


def effect_love(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: This is worth ○ points at the end of the game
    return True


def effect_moon(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: Whenever you have less than ○ cards in hand, draw back to ○
    return True


def effect_seas(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: Your alive peoples with power ○ or less are worth +1 points
    return True


def effect_fire(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: Your red events get +○
    return True


def effect_light(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: At the start of your turn, you may play a card with power ○ or less
    return True


def effect_sun(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: Your green wonders get +○
    return True


def effect_forgive(game: Game_State, card: Card, ui: any) -> bool:
    # Restore a people with power ○ or less
    power = card.effective_power()
    destroyed = [p for p in game.peoples if p.destroyed and p.effective_power() <= power]

    if not destroyed:
        ui.message("No destroyed peoples to restore.")
        return True

    selected = ui.select_card("Select a people to restore:", destroyed)
    if selected:
        selected.destroyed = False
        ui.message(f"{selected.name} was restored!")
    return True


def effect_unmaking(game: Game_State, card: Card, ui: any) -> bool:
    # Shuffle up to ○ green wonders into their owners' decks
    power = card.effective_power()
    targets = []
    for p in game.players:
        for w in p.wonders:
            if w.color == Card_Color.GREEN:
                targets.append((p, w))

    if not targets:
        ui.message("No green wonders to shuffle.")
        return True

    count = min(power, len(targets))
    selected = ui.select_multiple_targets(
        f"Select up to {count} green wonders to shuffle back:",
        [(f"{p.name}'s {w.name}", (p, w)) for p, w in targets],
        max_count=count
    )

    for player, wonder in selected:
        player.wonders.remove(wonder)
        wonder.counters = 0
        player.deck.append(wonder)
        random.shuffle(player.deck)
        ui.message(f"{wonder.name} shuffled into {player.name}'s deck.")
    return True


def effect_revolt(game: Game_State, card: Card, ui: any) -> bool:
    # Destroy a people with power ○ or less
    power = card.effective_power()
    targets = [p for p in game.peoples if p.effective_power() <= power and not p.destroyed]

    # Check for indestructible
    valid_targets = []
    for p in targets:
        if p.owner is None or not is_indestructible(game, p, p.owner):
            valid_targets.append(p)

    if not valid_targets:
        ui.message("No valid peoples to destroy.")
        return True

    selected = ui.select_card("Select a people to destroy:", valid_targets)
    if selected:
        selected.destroyed = True
        ui.message(f"{selected.name} was destroyed!")
    return True


def effect_blessing(game: Game_State, card: Card, ui: any) -> bool:
    # Add ○ +1 counters on a wonder
    power = card.effective_power()
    targets = []
    for p in game.players:
        targets.extend(p.wonders)

    if not targets:
        ui.message("No wonders to add counters to.")
        return True

    selected = ui.select_card("Select a wonder to add {} counters:".format(power), targets)
    if selected:
        selected.counters += power
        ui.message(f"Added {power} +1 counters to {selected.name}.")
    return True


def effect_stars(game: Game_State, card: Card, ui: any) -> bool:
    # Passive: When you draw cards, you may do ○ from the shared deck. They have power ○.
    return True


# Effect mapping
EFFECT_MAP: dict[str, Callable] = {
    "Rivers": effect_rivers,
    "Meteorite": effect_meteorite,
    "Earthquake": effect_earthquake,
    "Eruption": effect_eruption,
    "Miracle": effect_miracle,
    "Flashback": effect_flashback,
    "Prophecy": effect_prophecy,
    "Time Warp": effect_time_warp,
    "Aurora": effect_aurora,
    "Darkness": effect_darkness,
    "Spring": effect_spring,
    "Regrowth": effect_regrowth,
    "Wisdom": effect_wisdom,
    "Knowledge": effect_knowledge,
    "Sky": effect_sky,
    "Deserts": effect_deserts,
    "Forests": effect_forests,
    "Mountains": effect_mountains,
    "Flood": effect_flood,
    "Animals": effect_animals,
    "War": effect_war,
    "Love": effect_love,
    "Moon": effect_moon,
    "Seas": effect_seas,
    "Fire": effect_fire,
    "Light": effect_light,
    "Sun": effect_sun,
    "Forgive": effect_forgive,
    "Unmaking": effect_unmaking,
    "Revolt": effect_revolt,
    "Blessing": effect_blessing,
    "Stars": effect_stars,
}


def execute_card_effect(game: Game_State, card: Card, ui: any) -> bool:
    if card.name in EFFECT_MAP:
        return EFFECT_MAP[card.name](game, card, ui)
    return True


def draw_card(game: Game_State, player: Player, ui: any) -> Optional[Card]:
    if not player.deck:
        return None
    card = player.deck.pop()
    player.hand.append(card)
    ui.message(f"{player.name} drew {card.name}.")
    return card


def is_indestructible(game: Game_State, people: Card, owner_idx: int) -> bool:
    """Check if a people is protected by Mountains wonder."""
    player = game.players[owner_idx]
    for w in player.wonders:
        if w.name == "Mountains":
            if people.effective_power() <= w.effective_power():
                return True
    return False


def get_wonder_power_bonus(game: Game_State, player_idx: int, wonder: Card) -> int:
    """Calculate power bonuses from other wonders."""
    player = game.players[player_idx]
    bonus = 0

    for w in player.wonders:
        if w is wonder:
            continue
        # Wisdom: Your other blue wonders get +○
        if w.name == "Wisdom" and wonder.color == Card_Color.BLUE:
            bonus += w.effective_power()
        # Sun: Your green wonders get +○
        if w.name == "Sun" and wonder.color == Card_Color.GREEN:
            bonus += w.effective_power()

    return bonus


def get_event_power_bonus(game: Game_State, player_idx: int, event: Card) -> int:
    """Calculate power bonuses for events."""
    player = game.players[player_idx]
    bonus = 0

    for w in player.wonders:
        # Fire: Your red events get +○
        if w.name == "Fire" and event.color == Card_Color.RED:
            bonus += w.effective_power()

    return bonus


def get_event_power_penalty(game: Game_State, player_idx: int, event: Card) -> int:
    """Calculate power penalties from opponent's Sky wonder."""
    opponent = game.players[1 - player_idx]
    penalty = 0

    for w in opponent.wonders:
        # Sky: Opponent events get ○ down to a minimum of 1 power
        if w.name == "Sky":
            penalty += w.effective_power()

    return penalty
