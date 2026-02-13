from __future__ import annotations
import socket

from gods.models import Game_State, Choice, Card, Card_Id, effective_power
from gods.game import compute_player_score, detailed_str
from gods_online.protocol import send_message, recv_message


def serialize_card(game: Game_State, card: Card) -> dict:
    return {
        "id": card.id,
        "name": card.name,
        "card_type": card.card_type.value,
        "color": card.color.value,
        "power": effective_power(game, card),
        "base_power": card.power,
        "counters": card.counters,
        "effect": card.effect,
        "destroyed": card.destroyed,
        "owner": card.owner,
    }


def serialize_state_for_player(game: Game_State, viewer_index: int) -> dict:
    players = []
    for i, player in enumerate(game.players):
        p = {
            "name": player.name,
            "deck_count": len(player.deck),
            "discard_count": len(player.discard),
            "hand_count": len(player.hand),
            "wonders": [serialize_card(game, w) for w in player.wonders],
        }
        if i == viewer_index:
            p["hand"] = [serialize_card(game, c) for c in player.hand]
        else:
            p["hand"] = []
        players.append(p)

    return {
        "peoples": [serialize_card(game, p) for p in game.peoples],
        "players": players,
        "current_player": game.current_player,
        "scores": [compute_player_score(game, i) for i in range(len(game.players))],
    }


def assign_card_ids(game: Game_State) -> None:
    card_id = 0
    for player in game.players:
        for card_list in [player.deck, player.hand, player.discard, player.wonders]:
            for card in card_list:
                card.id = card_id
                card_id += 1
    for card in game.peoples:
        card.id = card_id
        card_id += 1
    for card in game.shared_deck:
        card.id = card_id
        card_id += 1


def serialize_all_cards(game: Game_State) -> list[dict]:
    cards = []
    for player in game.players:
        for card_list in [player.deck, player.hand, player.discard, player.wonders]:
            for card in card_list:
                cards.append(serialize_card(game, card))
    for card in game.peoples:
        cards.append(serialize_card(game, card))
    for card in game.shared_deck:
        cards.append(serialize_card(game, card))
    return cards


def serialize_zones(game: Game_State) -> dict:
    return {
        "p0_deck": [c.id for c in game.players[0].deck],
        "p0_hand": [c.id for c in game.players[0].hand],
        "p0_discard": [c.id for c in game.players[0].discard],
        "p0_wonders": [c.id for c in game.players[0].wonders],
        "p1_deck": [c.id for c in game.players[1].deck],
        "p1_hand": [c.id for c in game.players[1].hand],
        "p1_discard": [c.id for c in game.players[1].discard],
        "p1_wonders": [c.id for c in game.players[1].wonders],
        "peoples": [c.id for c in game.peoples],
    }


def serialize_action_card_ids(game: Game_State, choice: Choice, actions: list) -> list[int]:
    if choice.type != "choose-card":
        return []
    result = []
    for card_id in actions:
        if Card_Id.is_null(card_id):
            result.append(-1)
        else:
            card = game.get_card(card_id)
            result.append(card.id)
    return result


def serialize_actions(game: Game_State, choice: Choice, actions: list) -> list[str]:
    result = []
    if choice.type == "main":
        labels = {
            "play": "Play a card",
            "pass": "Pass (draw a card)",
            "end": "End the game",
        }
        for action in actions:
            result.append(labels.get(action, str(action)))
    elif choice.type == "choose-binary":
        result = [str(a) for a in actions]
    elif choice.type == "choose-card":
        for card_id in actions:
            if Card_Id.is_null(card_id):
                result.append("Done")
            else:
                card = game.get_card(card_id)
                result.append(detailed_str(card))
    else:
        result = [str(a) for a in actions]
    return result


class Agent_Remote:
    def __init__(self, conn: socket.socket, player_index: int):
        self.conn = conn
        self.player_index = player_index

    def message(self, msg: str):
        send_message(self.conn, {"type": "message", "text": msg})

    def choose_action(self, state: Game_State, choice: Choice, actions: list) -> int:
        if len(actions) <= 1:
            return 0

        # Send current game state
        state_data = serialize_state_for_player(state, self.player_index)
        zones = serialize_zones(state)
        all_cards = serialize_all_cards(state)
        send_message(self.conn, {
            "type": "state_update",
            "game_state": state_data,
            "zones": zones,
            "cards": all_cards,
        })

        # Send the choice request
        action_strings = serialize_actions(state, choice, actions)
        msg = {
            "type": "choose_action",
            "choice_type": choice.type,
            "actions": action_strings,
        }
        action_card_ids = serialize_action_card_ids(state, choice, actions)
        if action_card_ids:
            msg["action_card_ids"] = action_card_ids

        send_message(self.conn, msg)

        # Block waiting for client response
        response = recv_message(self.conn)
        index = response["index"]

        if not (0 <= index < len(actions)):
            return self.choose_action(state, choice, actions)

        return index
