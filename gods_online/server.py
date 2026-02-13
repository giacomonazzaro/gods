from __future__ import annotations
import socket
import sys

from gods.setup import quick_setup
from gods.game import game_loop, check_people_conditions, compute_player_score
from gods.agents.duel import Agent_Duel
from gods_online.agent_remote import Agent_Remote, serialize_state_for_player
from gods_online.protocol import send_message

DEFAULT_PORT = 9999


def run_server(host: str = "0.0.0.0", port: int = DEFAULT_PORT):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(2)
    print(f"Server listening on {host}:{port}")
    print("Waiting for Player 1...")

    conn0, addr0 = server_sock.accept()
    print(f"Player 1 connected from {addr0}")
    send_message(conn0, {
        "type": "welcome",
        "player_index": 0,
        "message": "You are Player 1. Waiting for Player 2...",
    })

    print("Waiting for Player 2...")
    conn1, addr1 = server_sock.accept()
    print(f"Player 2 connected from {addr1}")
    send_message(conn1, {
        "type": "welcome",
        "player_index": 1,
        "message": "You are Player 2. Game starting!",
    })
    send_message(conn0, {"type": "message", "text": "Player 2 connected. Game starting!"})

    # Setup game
    game = quick_setup()
    check_people_conditions(game)

    # Create network agents
    agent0 = Agent_Remote(conn0, player_index=0)
    agent1 = Agent_Remote(conn1, player_index=1)
    agent = Agent_Duel(agent0, agent1)

    # Display callback sends state to both players
    def display(state):
        for i, conn in enumerate([conn0, conn1]):
            state_data = serialize_state_for_player(state, i)
            send_message(conn, {"type": "state_update", "game_state": state_data})

    try:
        game_loop(game, agent, display)

        # Send final results
        score0 = compute_player_score(game, 0)
        score1 = compute_player_score(game, 1)
        for i, conn in enumerate([conn0, conn1]):
            send_message(conn, {
                "type": "game_over",
                "scores": [score0, score1],
                "final_state": serialize_state_for_player(game, i),
            })
    except ConnectionError as e:
        print(f"Connection lost: {e}")
    finally:
        conn0.close()
        conn1.close()
        server_sock.close()
        print("Server shut down.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run_server(port=port)
