from __future__ import annotations
import sys
import socket
import random
import threading

from pyray import *

from gods.setup import quick_setup
from gods.game import game_loop, compute_player_score
from gods.agents.duel import Agent_Duel

from kitchen_table.config import tweak
from kitchen_table.rendering import draw_table, color_from_tuple

from gods_graphical.agent_ui import Agent_UI, update_stacks
from gods_graphical.main import init_table_state, draw_hud, draw_highlighted_cards
from gods_graphical.ui import draw_buttons, draw_game_over_screen

from gods_online.protocol import recv_message
from gods_online.agent_remote import Agent_Remote, Agent_Local_Online

DEFAULT_PORT = 9999


def run_client(host: str = "localhost", port: int = DEFAULT_PORT):
    # Connect and receive init
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print(f"Connected to {host}:{port}")

    msg = recv_message(sock)
    seed = msg["seed"]
    player_index = msg["player_index"]
    print(f"You are Player {player_index + 1}. Seed: {seed}")

    # Setup game (same random state as opponent)
    random.seed(seed)
    gods_state = quick_setup()

    table_state = init_table_state(gods_state, bottom_player=player_index)
    table_state.draw_callback = lambda table: draw_hud(gods_state, table_state, bottom_player=player_index)

    # Window
    set_config_flags(ConfigFlags.FLAG_WINDOW_HIGHDPI)
    init_window(tweak["window_width"], tweak["window_height"], "Gods Online")
    set_target_fps(tweak["target_fps"])

    # Agents
    agent_ui = Agent_UI(table_state, bottom_player=player_index)
    agent_local = Agent_Local_Online(agent_ui, sock)
    agent_remote = Agent_Remote(sock)

    if player_index == 0:
        agent = Agent_Duel(agent_local, agent_remote)
    else:
        agent = Agent_Duel(agent_remote, agent_local)

    def display(state):
        update_stacks(table_state, gods_state, bottom_player=player_index)

    game_thread = threading.Thread(
        target=lambda: game_loop(gods_state, agent, display),
        daemon=True,
    )
    game_thread.start()

    from gods_graphical.main import run_app
    run_app(gods_state, table_state, agent_ui, player_index=player_index)

    sock.close()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    run_client(host, port)
