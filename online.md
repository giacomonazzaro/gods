Run the game:

- Terminal 1 — start the server:
python -m gods_online.server

- Terminal 2 — expose it with ngrok:
ngrok tcp 9999

- ngrok will show something like:
Forwarding  tcp://0.tcp.ngrok.io:12345 -> localhost:9999

- Send your friend the address (0.tcp.ngrok.io) and port (12345). They connect with:
python -m gods_online.client 0.tcp.ngrok.io 12345

- Then open a third terminal and connect yourself as player 1:
python -m gods_online.client