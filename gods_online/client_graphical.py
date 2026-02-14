from __future__ import annotations
import os
import sys
import socket
import threading
import queue

from pyray import *
import kitchen_table.models as kt
from kitchen_table.config import tweak
from kitchen_table.rendering import draw_table, color_from_tuple
from kitchen_table.game_state import update_card_positions
from gods_online.protocol import send_message, recv_message

DEFAULT_PORT = 9999


# --- UI helpers (same as agent_ui.py) ---

def point_in_rect(mx, my, x, y, w, h):
    return x <= mx <= x + w and y <= my <= y + h


class Button:
    def __init__(self, x, y, width, height, text=""):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text

    def pressed(self, mx, my, click):
        if not click:
            return False
        return point_in_rect(mx, my, self.x, self.y, self.width, self.height)


# --- Client state ---

class Client_State:
    def __init__(self):
        self.sock = None
        self.player_index = -1
        self.table_state = None
        self.cards_info = {}       # card_id -> dict with name, power, etc.
        self.scores = [0, 0]
        self.current_player = 0
        self.buttons = []
        self.highlighted_card_ids = []  # kt card IDs to highlight
        self.pending_choice = None      # the choose_action message, or None
        self.game_over = False
        self.game_over_msg = None
        self.message_queue = queue.Queue()
        # Zone-to-stack mapping (set on game_init based on player_index)
        self.zone_order = []


def init_table(client: Client_State, game_init_msg: dict):
    """Create the table state from the game_init message."""
    cards_data = game_init_msg["cards"]
    zones = game_init_msg["zones"]
    client.player_index = game_init_msg["player_index"]
    client.scores = game_init_msg["scores"]

    images_dir = os.path.join(os.path.dirname(__file__), "..", "gods", "cards", "card-images")

    def get_image_path(card_name):
        filename = card_name.lower().replace(" ", "_") + ".jpg"
        path = os.path.join(images_dir, filename)
        if os.path.exists(path):
            return path
        return None

    def draw_power(card: kt.Card):
        w = tweak["card_width"]
        h = tweak["card_height"]
        r = tweak["card_corner_radius"]
        info = client.cards_info.get(card.id, {})
        power = str(info.get("power", "?"))

        draw_circle(
            int(0.88 * w), int(0.12 * w), int(0.12 * w), Color(255, 255, 255, 255)
        )
        draw_text(
            power,
            int(0.83 * w),
            int(0.03 * w),
            int(0.2 * w),
            Color(0, 0, 0, 255),
        )

        if info.get("destroyed", False):
            draw_rectangle_rounded(
                Rectangle(0, 0, w, h), r / min(w, h), 8,
                (0, 0, 0, 100),
            )

    # Build card ID -> data mapping and create kt.Cards
    # Cards must be indexed by their ID, so we need a list big enough
    max_id = max(c["id"] for c in cards_data)
    kt_cards = [None] * (max_id + 1)

    for card_data in cards_data:
        cid = card_data["id"]
        client.cards_info[cid] = card_data
        kt_cards[cid] = kt.Card(
            id=cid,
            title=card_data["name"],
            description=card_data.get("effect", ""),
            image_path=get_image_path(card_data["name"]),
            draw_callback=draw_power,
        )

    # Layout positions from config
    deck_x = tweak["deck_x"]
    hand_x = tweak["hand_x"]
    discard_x = tweak["discard_x"]
    wonders_x = tweak["wonders_x"]
    peoples_x = tweak["peoples_x"]

    bottom_hand_y = tweak["player1_hand_y"]
    bottom_deck_y = tweak["player1_deck_y"]
    bottom_wonders_y = tweak["player1_wonders_y"]

    top_hand_y = tweak["player2_hand_y"]
    top_deck_y = tweak["player2_deck_y"]
    top_wonders_y = tweak["player2_wonders_y"]

    peoples_y = tweak["peoples_y"]

    spread_hand = tweak["hand_spread_x"]
    spread_wonders = tweak["wonders_spread_x"]
    spread_pile = tweak["pile_spread_y"]

    # Perspective: your cards at bottom, opponent at top
    if client.player_index == 0:
        bottom_prefix = "p0"
        top_prefix = "p1"
    else:
        bottom_prefix = "p1"
        top_prefix = "p0"

    # Stack order: bottom deck, hand, discard, wonders; top deck, hand, discard, wonders; peoples
    stack_defs = [
        (f"{bottom_prefix}_deck",    deck_x,    bottom_deck_y,    0,              spread_pile, False),
        (f"{bottom_prefix}_hand",    hand_x,    bottom_hand_y,    spread_hand,    0,           True),
        (f"{bottom_prefix}_discard", discard_x, bottom_deck_y,    0,              spread_pile, True),
        (f"{bottom_prefix}_wonders", wonders_x, bottom_wonders_y, spread_wonders, 0,           True),
        (f"{top_prefix}_deck",       deck_x,    top_deck_y,       0,              spread_pile, False),
        (f"{top_prefix}_hand",       hand_x,    top_hand_y,       spread_hand,    0,           False),
        (f"{top_prefix}_discard",    discard_x, top_deck_y,       0,              spread_pile, True),
        (f"{top_prefix}_wonders",    wonders_x, top_wonders_y,    spread_wonders, 0,           True),
        ("peoples",                  peoples_x, peoples_y,        spread_wonders, 0,           True),
    ]

    stacks = []
    client.zone_order = []
    for zone_name, sx, sy, spx, spy, face_up in stack_defs:
        card_ids = zones.get(zone_name, [])
        stack = kt.Stack(x=sx, y=sy, cards=list(card_ids), spread_x=spx, spread_y=spy, face_up=face_up)
        stacks.append(stack)
        client.zone_order.append(zone_name)

    client.table_state = kt.Table_State(cards=kt_cards, stacks=stacks)

    # Set initial card positions
    for stack in client.table_state.stacks:
        update_card_positions(stack, client.table_state)

    def table_draw_callback(table):
        # Bottom player score
        draw_text(
            f"points: {client.scores[client.player_index]}",
            90, 650, 40, Color(255, 255, 255, 255),
        )
        # Top player score
        draw_text(
            f"points: {client.scores[1 - client.player_index]}",
            90, 280, 40, Color(255, 255, 255, 255),
        )

    client.table_state.draw_callback = table_draw_callback


def update_from_state(client: Client_State, msg: dict):
    """Update table state from a state_update message."""
    if "zones" not in msg or client.table_state is None:
        return

    zones = msg["zones"]
    for i, zone_name in enumerate(client.zone_order):
        card_ids = zones.get(zone_name, [])
        client.table_state.stacks[i].cards = list(card_ids)
        update_card_positions(client.table_state.stacks[i], client.table_state)

    # Update card properties
    if "cards" in msg:
        for card_data in msg["cards"]:
            cid = card_data["id"]
            client.cards_info[cid] = card_data

    if "game_state" in msg and "scores" in msg["game_state"]:
        client.scores = msg["game_state"]["scores"]
    if "game_state" in msg and "current_player" in msg["game_state"]:
        client.current_player = msg["game_state"]["current_player"]


def setup_choice(client: Client_State, msg: dict):
    """Set up buttons/highlights for a choose_action message."""
    client.pending_choice = msg
    client.buttons = []
    client.highlighted_card_ids = []

    actions = msg["actions"]
    choice_type = msg["choice_type"]
    count = len(actions)
    button_w = 140
    button_h = 45
    gap = 20
    total_width = count * button_w + (count - 1) * gap
    start_x = (tweak["window_width"] - total_width) // 2
    button_y = tweak["window_height"] - 50

    if choice_type == "main":
        for i, action in enumerate(actions):
            x = start_x + i * (button_w + gap)
            client.buttons.append(Button(x, button_y, button_w, button_h, text=action))

    elif choice_type == "choose-binary":
        labels = actions if len(actions) == 2 else ["Yes", "No"]
        for i, label in enumerate(labels):
            x = start_x + i * (button_w + gap)
            client.buttons.append(Button(x, button_y, button_w, button_h, text=str(label)))

    elif choice_type == "choose-card":
        action_card_ids = msg.get("action_card_ids", [])
        for i, card_id in enumerate(action_card_ids):
            if card_id == -1:
                x = start_x
                client.buttons.append(Button(x, button_y, button_w, button_h, text="Done"))
            else:
                client.highlighted_card_ids.append(card_id)


def handle_click(client: Client_State, mx, my) -> int:
    """Check if a click resolves the pending choice. Returns action index or -1."""
    if client.pending_choice is None:
        return -1

    choice_type = client.pending_choice["choice_type"]

    if choice_type in ("main", "choose-binary"):
        for i, button in enumerate(client.buttons):
            if button.pressed(mx, my, True):
                return i

    elif choice_type == "choose-card":
        action_card_ids = client.pending_choice.get("action_card_ids", [])
        # Check buttons (Done)
        button_idx = 0
        for i, card_id in enumerate(action_card_ids):
            if card_id == -1:
                if button_idx < len(client.buttons) and client.buttons[button_idx].pressed(mx, my, True):
                    return i
                button_idx += 1
            else:
                # Check card click
                if client.table_state and client.table_state.animated_cards:
                    kt_card = client.table_state.animated_cards[card_id]
                    w = tweak["card_width"]
                    h = tweak["card_height"]
                    if point_in_rect(mx, my, kt_card.x, kt_card.y, w, h):
                        return i

    return -1


# --- Network thread ---

def network_thread(client: Client_State):
    try:
        while True:
            msg = recv_message(client.sock)
            client.message_queue.put(msg)
            if msg["type"] == "game_over":
                break
    except ConnectionError:
        client.message_queue.put({"type": "disconnected"})


# --- Main ---

def run_client(host: str = "localhost", port: int = DEFAULT_PORT):
    client = Client_State()
    client.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.sock.connect((host, port))
    print(f"Connected to {host}:{port}")

    # Start network thread
    net_thread = threading.Thread(target=network_thread, args=(client,), daemon=True)
    net_thread.start()

    # Wait for welcome + game_init before opening window
    while client.table_state is None:
        try:
            msg = client.message_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if msg["type"] == "welcome":
            print(msg["message"])
        elif msg["type"] == "message":
            print(msg["text"])
        elif msg["type"] == "game_init":
            init_table(client, msg)
            print(f"Game started! You are Player {client.player_index + 1}.")
        elif msg["type"] == "disconnected":
            print("Disconnected from server.")
            return

    # Open Raylib window, flag for high-DPI displays
    set_config_flags(ConfigFlags.FLAG_WINDOW_HIGHDPI)
    init_window(tweak["window_width"], tweak["window_height"], "Gods Online")
    set_target_fps(tweak["target_fps"])

    while not window_should_close() and not client.game_over:
        # Process network messages
        while not client.message_queue.empty():
            try:
                msg = client.message_queue.get_nowait()
            except queue.Empty:
                break

            if msg["type"] == "state_update":
                update_from_state(client, msg)
            elif msg["type"] == "choose_action":
                setup_choice(client, msg)
            elif msg["type"] == "message":
                print(msg["text"])
            elif msg["type"] == "game_over":
                client.game_over = True
                client.game_over_msg = msg
                client.pending_choice = None
                client.buttons = []
                client.highlighted_card_ids = []
                if "final_state" in msg:
                    update_from_state(client, {
                        "game_state": msg["final_state"],
                        "zones": msg.get("zones", {}),
                        "cards": msg.get("cards", []),
                    })
                client.scores = msg["scores"]
            elif msg["type"] == "disconnected":
                client.game_over = True

        # Handle input
        if client.pending_choice is not None and is_mouse_button_pressed(MouseButton.MOUSE_BUTTON_LEFT):
            mx, my = get_mouse_x(), get_mouse_y()
            selected = handle_click(client, mx, my)
            if selected >= 0:
                send_message(client.sock, {"type": "action_response", "index": selected})
                client.pending_choice = None
                client.buttons = []
                client.highlighted_card_ids = []

        # Render
        begin_drawing()
        clear_background(color_from_tuple(tweak["background_color"]))

        if client.table_state is not None:
            draw_table(client.table_state)

        # Draw buttons
        for button in client.buttons:
            color = color_from_tuple(tweak["button_color"])
            draw_rectangle_rounded(
                Rectangle(button.x, button.y, button.width, button.height), 0.3, 8, color,
            )
            text_width = measure_text(button.text, 20)
            text_x = button.x + (button.width - text_width) // 2
            text_y = button.y + (button.height - 20) // 2
            draw_text(button.text, text_x, text_y, 20, color_from_tuple(tweak["button_text_color"]))

        # Draw card highlights
        if client.table_state and client.table_state.animated_cards:
            for card_id in client.highlighted_card_ids:
                kt_card = client.table_state.animated_cards[card_id]
                w = tweak["card_width"]
                h = tweak["card_height"]
                draw_rectangle_rounded_lines_ex(
                    Rectangle(kt_card.x, kt_card.y, w, h), 0.25, 8, 4, (255, 255, 255, 100),
                )

        end_drawing()

    # Game over screen — keep window open until closed
    if client.game_over_msg:
        scores = client.game_over_msg["scores"]
        pi = client.player_index
        if scores[pi] > scores[1 - pi]:
            result_text = "You win!"
        elif scores[pi] < scores[1 - pi]:
            result_text = "You lose!"
        else:
            result_text = "It's a tie!"

        while not window_should_close():
            begin_drawing()
            clear_background(color_from_tuple(tweak["background_color"]))
            if client.table_state is not None:
                draw_table(client.table_state)
            # Overlay
            draw_rectangle(0, 0, tweak["window_width"], tweak["window_height"], (0, 0, 0, 150))
            draw_text("GAME OVER", 600, 350, 60, Color(255, 255, 255, 255))
            draw_text(result_text, 640, 430, 40, Color(255, 215, 0, 255))
            draw_text(
                f"Player 1: {scores[0]}  |  Player 2: {scores[1]}",
                540, 490, 30, Color(200, 200, 200, 255),
            )
            end_drawing()

    close_window()
    client.sock.close()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    run_client(host, port)
