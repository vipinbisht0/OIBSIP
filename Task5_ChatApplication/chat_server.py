"""
Chat Application - Server (Advanced Tier)
--------------------------------------------
Handles multiple client connections over TCP sockets.
Features:
- User registration and login (username + password, stored in SQLite, hashed)
- Multiple named chat rooms
- Message history per room (loaded from SQLite when a user joins)
- Real-time, bidirectional broadcast of messages to all clients in a room
- Graceful disconnect handling with notifications

Protocol: Each message sent over the socket is a single JSON object,
terminated by a newline character ("\n"). This makes it easy to read
one complete message at a time from the socket stream.

SECURITY NOTE: Messages are sent as plain-text JSON over a raw TCP
socket. There is NO encryption (no TLS/SSL) on this connection. This
is fine for local/learning use on localhost, but should never be used
to send real sensitive data over an untrusted network. Passwords are
hashed (SHA-256 + per-user salt) before being stored in the database,
but they ARE sent in plain text over the socket during login/register.
"""

import socket
import threading
import json
import sqlite3
import hashlib
import secrets
import datetime

HOST = "localhost"
PORT = 5555
DB_PATH = "chat_history.db"

# clients: maps socket -> {"username": str, "room": str}
clients = {}
clients_lock = threading.Lock()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def register_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE username = ?", (username,))
    if cur.fetchone():
        conn.close()
        return False, "Username already exists."

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)
    cur.execute(
        "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
        (username, password_hash, salt),
    )
    conn.commit()
    conn.close()
    return True, "Registration successful."


def authenticate_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT password_hash, salt FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False, "Username not found."

    stored_hash, salt = row
    if hash_password(password, salt) == stored_hash:
        return True, "Login successful."
    return False, "Incorrect password."


def save_message(room, username, content):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    timestamp = datetime.datetime.now().strftime("%H:%M")
    cur.execute(
        "INSERT INTO messages (room, username, content, timestamp) VALUES (?, ?, ?, ?)",
        (room, username, content, timestamp),
    )
    conn.commit()
    conn.close()


def get_room_history(room, limit=50):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT username, content, timestamp FROM messages WHERE room = ? ORDER BY id DESC LIMIT ?",
        (room, limit),
    )
    rows = cur.fetchall()
    conn.close()
    rows.reverse()  # oldest first
    return [{"username": u, "content": c, "timestamp": t} for u, c, t in rows]


def send_json(sock, data):
    """Send a dict as a newline-terminated JSON message."""
    try:
        message = json.dumps(data) + "\n"
        sock.sendall(message.encode("utf-8"))
    except OSError:
        pass  # socket already closed


def broadcast_to_room(room, data, exclude_sock=None):
    with clients_lock:
        for sock, info in clients.items():
            if info.get("room") == room and sock != exclude_sock:
                send_json(sock, data)


def handle_client(sock, addr):
    buffer = ""
    username = None
    room = None

    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break  # client disconnected

            buffer += chunk.decode("utf-8")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                action = msg.get("action")

                if action == "register":
                    success, info_msg = register_user(msg["username"], msg["password"])
                    send_json(sock, {"action": "register_result", "success": success, "message": info_msg})

                elif action == "login":
                    success, info_msg = authenticate_user(msg["username"], msg["password"])
                    if success:
                        username = msg["username"]
                        with clients_lock:
                            clients[sock] = {"username": username, "room": None}
                    send_json(sock, {"action": "login_result", "success": success, "message": info_msg})

                elif action == "join_room":
                    if not username:
                        continue
                    room = msg["room"]
                    with clients_lock:
                        clients[sock]["room"] = room

                    history = get_room_history(room)
                    send_json(sock, {"action": "room_history", "room": room, "history": history})

                    join_notice = {
                        "action": "message",
                        "room": room,
                        "username": "System",
                        "content": f"{username} has joined the room.",
                        "timestamp": datetime.datetime.now().strftime("%H:%M"),
                    }
                    broadcast_to_room(room, join_notice, exclude_sock=sock)

                elif action == "message":
                    if not username or not room:
                        continue
                    content = msg["content"]
                    save_message(room, username, content)
                    timestamp = datetime.datetime.now().strftime("%H:%M")
                    payload = {
                        "action": "message",
                        "room": room,
                        "username": username,
                        "content": content,
                        "timestamp": timestamp,
                    }
                    broadcast_to_room(room, payload)  # send to everyone including sender for confirmation

    except (ConnectionResetError, ConnectionAbortedError):
        pass
    finally:
        with clients_lock:
            clients.pop(sock, None)
        if username and room:
            leave_notice = {
                "action": "message",
                "room": room,
                "username": "System",
                "content": f"{username} has disconnected.",
                "timestamp": datetime.datetime.now().strftime("%H:%M"),
            }
            broadcast_to_room(room, leave_notice)
        sock.close()
        print(f"[DISCONNECTED] {addr} ({username or 'unauthenticated'})")


def main():
    init_db()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen()

    print(f"[LISTENING] Chat server running on {HOST}:{PORT}")

    while True:
        client_sock, addr = server_sock.accept()
        print(f"[CONNECTED] {addr}")
        thread = threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True)
        thread.start()


if __name__ == "__main__":
    main()
