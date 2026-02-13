from __future__ import annotations
import json
import struct
import socket

HEADER_SIZE = 4  # 4 bytes for message length (uint32, big-endian)


def send_message(sock: socket.socket, data: dict) -> None:
    body = json.dumps(data).encode("utf-8")
    header = struct.pack("!I", len(body))
    sock.sendall(header + body)


def recv_message(sock: socket.socket) -> dict:
    header = _recv_exact(sock, HEADER_SIZE)
    length = struct.unpack("!I", header)[0]
    body = _recv_exact(sock, length)
    return json.loads(body.decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data
