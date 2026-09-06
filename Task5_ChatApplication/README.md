[README_Task5.md](https://github.com/user-attachments/files/31875588/README_Task5.md)
# Task 5 - Chat Application

## Objective
A real-time messaging application in Python. This is the **Advanced Tier** implementation: a full GUI chat application with multiple rooms, user authentication, and message history.

## Tech Stack
- Python 3
- `socket` — TCP networking between server and clients
- `threading` — handling multiple connected clients concurrently
- `tkinter` — GUI for the client application
- `sqlite3` — storing user accounts and message history
- `hashlib` / `secrets` — password hashing (SHA-256 with per-user salt)
- `json` — message protocol between client and server

## Files
- `chat_server.py` — the server. Run this first; it listens for client connections.
- `chat_client.py` — the GUI client. Run one instance per user who wants to chat.

## Features
- GUI chat window built with `tkinter`, with a custom dark theme
- User registration and login (username + password, hashed and stored in SQLite — passwords are never stored in plain text)
- Multiple named chat rooms — users can create or join any room by typing its name
- Message history: past messages in a room are loaded automatically when a user joins
- Real-time, bidirectional message exchange between all clients in the same room
- Messages displayed with a timestamp prefix, e.g. `[14:35] Alice: Hello`
- Graceful disconnection handling: other users in the room are notified when someone leaves
- Emoji shortcode support: type things like `:smile:` `:heart:` `:fire:` `:thumbsup:` `:wave:` `:party:` and they render as real emoji
- Desktop-style notification: the window title flashes "🔔 New message!" when a message arrives while the window is not focused
- Runs entirely on `localhost` — multiple client windows on the same machine can chat with each other

## How to Run

1. Start the server first (leave this terminal running):
```bash
python3 chat_server.py
```
You should see:
```
[LISTENING] Chat server running on localhost:5555
```

2. In a separate terminal, start a client:
```bash
python3 chat_client.py
```
Register a username and password, log in, then join a room (e.g. `general`).

3. To simulate a conversation, open another terminal and run `chat_client.py` again with a different username, joining the same room. Messages sent from either window appear instantly in both.

## Security & Data Storage (Transparency Note)

- **No encryption**: All communication between the client and server happens over a plain TCP socket. There is **no TLS/SSL encryption** on this connection. Messages, usernames, and passwords are sent as readable JSON text over the socket during transmission.
- **Password storage**: Passwords are **not** stored in plain text. Each password is combined with a random per-user salt and hashed using SHA-256 before being saved to the SQLite database (`chat_history.db`).
- **Message storage**: All chat messages are stored permanently in the local SQLite database (`chat_history.db`) so that room history can be loaded when a user joins. Messages are stored as plain text in the database — they are not encrypted at rest.
- **Intended use**: This project is for local/learning purposes (e.g. on `localhost` or a trusted local network). It should not be used to transmit sensitive real-world data over an untrusted network, since there is no encryption in transit.

## Author
Submitted as part of the Oasis Infobyte Python Programming Internship (OIBSIP).
