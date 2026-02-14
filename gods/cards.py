from __future__ import annotations
from dataclasses import dataclass
import itertools
from gods.models import Card, Card_Id, Card_Type, Card_Color, Game_State, effective_power, Choice
from gods.game import *

def create_card(data: dict, default_power: int = 3) -> Card:
    card_type = Card_Type(data["type"])
    color = Card_Color(data["color"])
    # Use the power from data if it's a people card (they have fixed power), otherwise use default
    power = data["power"] if card_type == Card_Type.PEOPLE else default_power
    name = data["name"]

    # Use specialized card class if available (defined at bottom of file)
    # Import here to avoid forward reference issues
    card_class = _get_card_class(name)
    return card_class(
        name=name,
        card_type=card_type,
        power=power,
        color=color,
        effect=data["effect"]
    )


def _get_card_class(name: str) -> type:
    """Get the card class for a given card name. Returns base Card if no specialized class."""
    # CARD_CLASSES is defined at the bottom of the file after all classes
    if name in CARD_CLASSES:
        return CARD_CLASSES[name]
    return Card



def is_indestructible(game: Game_State, people: Card, owner_idx: int) -> bool:
    """Check if a people is protected by Mountains wonder."""
    player = game.players[owner_idx]
    for w in player.wonders:
        if w.name == "Mountains":
            if effective_power(game, people) <= effective_power(game, w):
                return True
    return False

def all_combinations(card_ids: list[Card_Id], num_cards: int, up_to: bool) -> list[tuple]:
    num_cards = min(num_cards, len(card_ids))
    if up_to:
        combinations = []
        for k in range(0, num_cards + 1):
            combinations += itertools.combinations(card_ids, k)
        return combinations
    else:
        if len(card_ids) <= num_cards:
            return [tuple(card_ids)]
        return list(itertools.combinations(card_ids, num_cards))


# Card classes with specialized effects

@dataclass
class Light(Card):
    """When you end the game, you may play a card with power <= X"""
    def get_card_selection(self, state: Game_State) -> list[Card_Id]:
        result = []
        for i, card in enumerate(state.players[self.owner].hand):
            if effective_power(state, card) <= effective_power(state, self):
                result.append(Card_Id(area="hand", card_index=i, owner_index=self.owner))
        result.append(Card_Id.null())
        return result

    def on_game_end(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = self.owner
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            if not Card_Id.is_null(card_id):
                return play_card(state, card_id)
            return []

        choice.resolve = resolve
        return [choice]

@dataclass
class Moon(Card):
    def draw_back_up(self, game: Game_State) -> list[Choice]:
        player = game.players[self.owner]
        choices = []
        while len(player.hand) <= effective_power(game, self):
            choices.extend(draw_card(game, self.owner))
        return choices

@dataclass
class War(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        for people in game.peoples:
            if not people.destroyed and effective_power(game, people) <= effective_power(game, self):
                card_id = Card_Id(area="people", card_index=game.peoples.index(people), owner_index=people.owner)
                result.append(card_id)
        result.append(Card_Id.null())
        return result

    def on_pass(self, game: Game_State) -> list[Choice]:
        # Only trigger for the player who owns War
        if game.current_player != self.owner:
            return []

        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            if not Card_Id.is_null(card_id):
                destroy_people(state, card_id)
            return []

        choice.resolve = resolve
        return [choice]

@dataclass
class Rivers(Card):
    # When you pass, you may restore a people with power <= X.
    def on_pass(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            targets = []
            for (i, people) in enumerate(state.peoples):
                if people.destroyed:
                    targets.append(Card_Id(area="people", card_index=i, owner_index=people.owner))
            targets.append(Card_Id.null())
            return targets
        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            if not Card_Id.is_null(card_id):
                restore_people(state, card_id)
            return []
        choice.resolve = resolve
        return [choice]

@dataclass
class Earthquake(Card):
    def on_played(self, game: Game_State) -> list[Choice]:
        power = effective_power(game, self)
        for people_id in game.peoples_ids():
            people = game.get_card(people_id)
            if effective_power(game, people) <= power:
                destroy_people(game, people_id)
        return []

@dataclass
class Eruption(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        targets = []
        power = effective_power(game, self)
        for (player_id, p) in enumerate(game.players):
            for (i, w) in enumerate(p.wonders):
                if w.color == Card_Color.BLUE:
                    card_id = Card_Id(area="wonders", card_index=i, owner_index=player_id)
                    targets.append(card_id)
        return targets

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-cards"

        eruption = self
        def generate_actions(state: Game_State, choice: Choice) -> list:
            power = effective_power(state, eruption)
            return all_combinations(eruption.get_card_selection(state), power, up_to=True)

        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            combination = actions[option_index]
            cards = [state.get_card(card_id) for card_id in combination]
            for card in cards:
                player = state.players[card.owner]
                idx = player.wonders.index(card)
                shuffle_card_into_deck(state, Card_Id(area="wonders", card_index=idx, owner_index=card.owner))
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Meteorite(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        power = effective_power(game, self)
        for (i, people) in enumerate(game.peoples):
            if people.owner == (1 - game.current_player) and not people.destroyed:
                if effective_power(game, people) <= power:
                    card_id = Card_Id(area="people", card_index=i, owner_index=people.owner)
                    result.append(card_id)
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        targets = self.get_card_selection(game)
        for target in targets:
            destroy_people(game, target)
        return []


@dataclass
class Miracle(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        player = game.players[game.current_player]
        for (i, card) in enumerate(player.hand):
            if card.card_type == Card_Type.EVENT:
                card_id = Card_Id(area="hand", card_index=i, owner_index=game.current_player)
                result.append(card_id)
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        miracle_card = self
        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            card = state.get_card(card_id)
            bonus = effective_power(state, miracle_card)
            card.counters += bonus
            return play_card(state, card_id)

        choice.resolve = resolve
        return [choice]


@dataclass
class Flashback(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        player = game.players[game.current_player]
        for (i, card) in enumerate(player.discard):
            if card.card_type == Card_Type.EVENT:
                card_id = Card_Id(area="discard", card_index=i, owner_index=game.current_player)
                result.append(card_id)
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-cards"

        flashback = self
        def generate_actions(state: Game_State, choice: Choice) -> list:
            card_ids = flashback.get_card_selection(state)
            power = effective_power(state, flashback)
            return all_combinations(card_ids, power, up_to=True)

        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            combination = actions[option_index]
            cards = [state.get_card(card_id) for card_id in combination]
            player = state.players[state.current_player]
            for card in cards:
                player.discard.remove(card)
                player.hand.append(card)
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Prophecy(Card):
    """ Play up to X extra cards """
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        hand_size = len(game.players[self.owner].hand)
        result = [Card_Id(area="hand", card_index=i, owner_index=self.owner) for i in range(hand_size)]
        result.append(Card_Id.null())
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        return self._make_nth_choice(game, 0)

    def _make_nth_choice(self, game: Game_State, n: int) -> list[Choice]:
        power = effective_power(game, self)
        if n >= power:
            return []

        choice = Choice(player_index=self.owner)
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        prophecy = self
        def make_resolve(iteration):
            def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
                actions = choice.generate_actions(state, choice)
                card_id = actions[option_index]
                result: list[Choice] = []
                if not Card_Id.is_null(card_id):
                    result.extend(play_card(state, card_id))
                    result.extend(prophecy._make_nth_choice(state, iteration + 1))
                return result
            return resolve

        choice.resolve = make_resolve(n)
        return [choice]


@dataclass
class Time_Warp(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        targets = []
        for (player_id, p) in enumerate(game.players):
            for (i, w) in enumerate(p.wonders):
                card_id = Card_Id(area="wonders", card_index=i, owner_index=player_id)
                targets.append(card_id)
        return targets

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-cards"

        time_warp = self
        def generate_actions(state: Game_State, choice: Choice) -> list:
            power = effective_power(state, time_warp)
            card_ids = time_warp.get_card_selection(state)
            return all_combinations(card_ids, power, up_to=True)

        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            combination = actions[option_index]
            cards = [state.get_card(card_id) for card_id in combination]
            for card in cards:
                player = state.players[card.owner]
                player.wonders.remove(card)
                card.counters = 0
                player.hand.append(card)
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Aurora(Card):
    def on_played(self, game: Game_State) -> list[Choice]:
        power = effective_power(game, self)
        result = []
        for _ in range(power):
            result.extend(draw_card(game, game.current_player))
        return result


@dataclass
class Darkness(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        opponent_idx = 1 - self.owner
        opponent = game.players[opponent_idx]
        for (i, card) in enumerate(opponent.hand):
            card_id = Card_Id(area="hand", card_index=i, owner_index=opponent_idx)
            result.append(card_id)
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = 1 - self.owner  # Opponent chooses
        choice.type = "choose-cards"

        darkness = self
        def generate_actions(state: Game_State, choice: Choice) -> list:
            card_ids = darkness.get_card_selection(state)
            power = effective_power(state, darkness)
            return all_combinations(card_ids, power, up_to=False)

        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            combination = actions[option_index]
            cards = [state.get_card(card_id) for card_id in combination]
            opponent_idx = 1 - darkness.owner
            for card in cards:
                idx = state.players[opponent_idx].hand.index(card)
                discard_card(state, Card_Id(area="hand", card_index=idx, owner_index=opponent_idx))
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Spring(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        for (i, people) in enumerate(game.peoples):
            if not people.destroyed:
                card_id = Card_Id(area="people", card_index=i, owner_index=people.owner)
                result.append(card_id)
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        spring_card = self
        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            card = state.get_card(card_id)
            card.counters += effective_power(state, spring_card)
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Regrowth(Card):
    """Restore a people with power <= X"""
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        power = effective_power(game, self)
        for (i, people) in enumerate(game.peoples):
            if people.destroyed and effective_power(game, people) <= power:
                card_id = Card_Id(area="people", card_index=i, owner_index=people.owner)
                result.append(card_id)
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            people = state.get_card(card_id)
            people.destroyed = False
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Flood(Card):
    """Put X -1 counters on all people"""
    def on_played(self, game: Game_State) -> list[Choice]:
        power = effective_power(game, self)
        for people in game.peoples:
            people.counters -= power
        return []


@dataclass
class Forgive(Card):
    """Add X +1 counters on a people"""
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        for (i, people) in enumerate(game.peoples):
            card_id = Card_Id(area="people", card_index=i, owner_index=people.owner)
            result.append(card_id)
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        forgive_card = self
        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            people = state.get_card(card_id)
            people.counters += effective_power(state, forgive_card)
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Unmaking(Card):
    """Destroy a wonder with power <= X"""
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        targets = []
        power = effective_power(game, self)
        for (player_id, p) in enumerate(game.players):
            for (i, w) in enumerate(p.wonders):
                if effective_power(game, w) <= power:
                    card_id = Card_Id(area="wonders", card_index=i, owner_index=player_id)
                    targets.append(card_id)
        return targets

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            destroy_wonder(state, card_id)
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Revolt(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        power = effective_power(game, self)
        for (i, people) in enumerate(game.peoples):
            if not people.destroyed and effective_power(game, people) <= power:
                card_id = Card_Id(area="people", card_index=i, owner_index=people.owner)
                result.append(card_id)
        return result

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            destroy_people(state, card_id)
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Blessing(Card):
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        targets = []
        for (player_id, p) in enumerate(game.players):
            for (i, w) in enumerate(p.wonders):
                card_id = Card_Id(area="wonders", card_index=i, owner_index=player_id)
                targets.append(card_id)
        return targets

    def on_played(self, game: Game_State) -> list[Choice]:
        choice = Choice()
        choice.player_index = game.current_player
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        blessing_card = self
        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            card = state.get_card(card_id)
            card.counters += effective_power(state, blessing_card)
            return []

        choice.resolve = resolve
        return [choice]


# Passive wonders - these use hooks rather than on_played

@dataclass
class Wisdom(Card):
    """When you pass, you may play a card with power <= X"""
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        player = game.players[self.owner]
        power = effective_power(game, self)
        for (i, card) in enumerate(player.hand):
            if card.power <= power and card.card_type != Card_Type.PEOPLE:
                card_id = Card_Id(area="hand", card_index=i, owner_index=self.owner)
                result.append(card_id)
        result.append(Card_Id.null())
        return result

    def on_pass(self, game: Game_State) -> list[Choice]:
        if game.current_player != self.owner:
            return []

        choice = Choice()
        choice.player_index = self.owner
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            if not Card_Id.is_null(card_id):
                return play_card(state, card_id)
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Knowledge(Card):
    """Opponent events get -X, down to a minimum of 1 power"""
    def power_modifier(self, game: Game_State, card: Card, power: int) -> int:
        if card.card_type == Card_Type.EVENT:
            # Check if card belongs to opponent
            opponent_idx = 1 - self.owner
            if card in game.players[opponent_idx].hand:
                reduction = effective_power(game, self)
                return max(1, power - reduction)
        return power


@dataclass
class Sky(Card):
    """Your other blue wonders get +X"""
    def power_modifier(self, game: Game_State, card: Card, power: int) -> int:
        if card.color == Card_Color.BLUE and card != self:
            if card in game.players[self.owner].wonders:
                return power + effective_power(game, self)
        return power


@dataclass
class Deserts(Card):
    """You can score destroyed peoples with power X or less"""
    def on_scoring_people(self, game: Game_State, people: Card, points: int) -> int:
        if people.destroyed and people.owner == self.owner:
            if effective_power(game, people) <= effective_power(game, self):
                return people.eval_points(game, self.owner)
        return points


@dataclass
class Forests(Card):
    """When you pass, you may restore a people with power <= X"""
    def get_card_selection(self, game: Game_State) -> list[Card_Id]:
        result = []
        power = effective_power(game, self)
        for (i, people) in enumerate(game.peoples):
            if people.destroyed and effective_power(game, people) <= power:
                card_id = Card_Id(area="people", card_index=i, owner_index=people.owner)
                result.append(card_id)
        result.append(Card_Id.null())
        return result

    def on_pass(self, game: Game_State) -> list[Choice]:
        if game.current_player != self.owner:
            return []

        choice = Choice()
        choice.player_index = self.owner
        choice.type = "choose-card"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return self.get_card_selection(state)
        choice.generate_actions = generate_actions

        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            actions = choice.generate_actions(state, choice)
            card_id = actions[option_index]
            if not Card_Id.is_null(card_id):
                people = state.get_card(card_id)
                people.destroyed = False
            return []

        choice.resolve = resolve
        return [choice]


@dataclass
class Mountains(Card):
    """Your peoples with power X or less are indestructible"""
    def is_indestructible(self, game: Game_State, people: Card) -> bool:
        if people.owner == self.owner:
            if effective_power(game, people) <= effective_power(game, self):
                return True
        return False


@dataclass
class Animals(Card):
    """This is worth X points at the end of the game"""
    def on_scoring(self, game: Game_State) -> int:
        return effective_power(game, self)


@dataclass
class Love(Card):
    """Your peoples are worth X points extra"""
    def on_scoring_people(self, game: Game_State, people: Card, points: int) -> int:
        if people.owner == self.owner and not people.destroyed:
            return points + effective_power(game, self)
        return points

@dataclass
class Seas(Card):
    """Your alive peoples with power X or less are worth +1 points"""
    def on_scoring_people(self, game: Game_State, people: Card, points: int) -> int:
        if people.owner == self.owner and not people.destroyed:
            if effective_power(game, people) <= effective_power(game, self):
                return points + 1
        return points


@dataclass
class Fire(Card):
    """Your red events get +X"""
    def power_modifier(self, game: Game_State, card: Card, power: int) -> int:
        if card.card_type == Card_Type.EVENT and card.color == Card_Color.RED:
            if card in game.players[self.owner].hand:
                return power + effective_power(game, self)
        return power


@dataclass
class Sun(Card):
    """Your green wonders get +X"""
    def power_modifier(self, game: Game_State, card: Card, power: int) -> int:
        if card.color == Card_Color.GREEN and card != self:
            if card in game.players[self.owner].wonders:
                return power + effective_power(game, self)
        return power


@dataclass
class Stars(Card):
    """When you draw cards, you may draw from the shared deck."""
    def on_draw_replacement(self, game: Game_State) -> list[Choice]:
        if game.current_player != self.owner:
            return []
        if not game.shared_deck:
            return []

        choice = Choice()
        choice.player_index = self.owner
        choice.type = "choose-binary"

        def generate_actions(state: Game_State, choice: Choice) -> list:
            return ["Draw from shared deck", "Draw normally"]
        choice.generate_actions = generate_actions

        stars_card = self
        def resolve(state: Game_State, choice: Choice, option_index: int) -> list[Choice]:
            player_id = stars_card.owner
            if option_index == 0:
                power = effective_power(state, stars_card)
                player = state.players[player_id]
                card = state.shared_deck.pop()
                card.power = power
                card.owner = self.owner
                player.hand.append(card)
                return []
            else:
                return draw_card(state, player_id, replacement_effects=False)

        choice.resolve = resolve
        return [choice]


# People card classes - each implements their own condition for ownership

@dataclass
class Egyptians(Card):
    """You have the most total power among green wonders"""
    def eval_points(self, game: Game_State, player_index: int) -> int:
        scores = [0, 0]
        for i, player in enumerate(game.players):
            scores[i] = sum(
                effective_power(game, w)
                for w in player.wonders if w.color == Card_Color.GREEN
            )

        points = effective_power(game, self)
        if scores[player_index] > scores[1 - player_index]:
            return points
        else:
            return 0


@dataclass
class Greeks(Card):
    """You have twice or more cards in hand than the opponent"""
    def eval_points(self, game: Game_State, player_index: int) -> int:
        player = game.players[player_index]
        opponent = game.players[1 - player_index]
        if len(player.hand) >= 2 * len(opponent.hand) and len(opponent.hand) > 0:
            points = effective_power(game, self)
            return points
        return 0


@dataclass
class Vikings(Card):
    """You have the most cards in your deck"""
    def eval_points(self, game: Game_State, player_index: int) -> int:
        scores = [0, 0]
        for i, player in enumerate(game.players):
            scores[i] = len(player.deck)

        points = effective_power(game, self)
        if scores[player_index] > scores[1 - player_index]:
            return points
        else:
            return 0


@dataclass
class Minoans(Card):
    """You have the most wonders"""
    def eval_points(self, game: Game_State, player_index: int) -> int:
        scores = [0, 0]
        for i, player in enumerate(game.players):
            scores[i] = len(player.wonders)

        points = effective_power(game, self)
        if scores[player_index] > scores[1 - player_index]:
            return points
        else:
            return 0


@dataclass
class Babylonians(Card):
    """You have the most total power among wonders"""
    def eval_points(self, game: Game_State, player_index: int) -> int:
        scores = [0, 0]
        for i, player in enumerate(game.players):
            scores[i] = sum(
                effective_power(game, w)
                for w in player.wonders
            )

        points = effective_power(game, self)
        if scores[player_index] > scores[1 - player_index]:
            return points
        else:
            return 0


@dataclass
class Romans(Card):
    """You have the most total power among red wonders"""
    def eval_points(self, game: Game_State, player_index: int) -> int:
        scores = [0, 0]
        for i, player in enumerate(game.players):
            scores[i] = sum(
                effective_power(game, w)
                for w in player.wonders if w.color == Card_Color.RED
            )

        points = effective_power(game, self)
        if scores[player_index] > scores[1 - player_index]:
            return points
        else:
            return 0


@dataclass
class Judeans(Card):
    """You have the most total power among blue wonders"""
    def eval_points(self, game: Game_State, player_index: int) -> int:
        scores = [0, 0]
        for i, player in enumerate(game.players):
            scores[i] = sum(
                effective_power(game, w)
                for w in player.wonders if w.color == Card_Color.BLUE
            )

        points = effective_power(game, self)
        if scores[player_index] > scores[1 - player_index]:
            return points
        else:
            return 0


# Registry mapping card names to their specialized classes
CARD_CLASSES: dict[str, type] = {
    "Light": Light,
    "Moon": Moon,
    "War": War,
    "Rivers": Rivers,
    "Earthquake": Earthquake,
    "Eruption": Eruption,
    "Meteorite": Meteorite,
    "Miracle": Miracle,
    "Flashback": Flashback,
    "Prophecy": Prophecy,
    "Time Warp": Time_Warp,
    "Aurora": Aurora,
    "Darkness": Darkness,
    "Spring": Spring,
    "Regrowth": Regrowth,
    "Flood": Flood,
    "Forgive": Forgive,
    "Unmaking": Unmaking,
    "Revolt": Revolt,
    "Blessing": Blessing,
    "Wisdom": Wisdom,
    "Knowledge": Knowledge,
    "Sky": Sky,
    "Deserts": Deserts,
    "Forests": Forests,
    "Mountains": Mountains,
    "Animals": Animals,
    "Love": Love,
    "Seas": Seas,
    "Fire": Fire,
    "Sun": Sun,
    "Stars": Stars,
    # People cards
    "Egyptians": Egyptians,
    "Greeks": Greeks,
    "Vikings": Vikings,
    "Minoans": Minoans,
    "Babylonians": Babylonians,
    "Romans": Romans,
    "Judeans": Judeans,
}
