"""
Chat Application - Client (Advanced Tier)
--------------------------------------------
A tkinter GUI client for the chat server. Supports:
- User registration and login
- Joining/creating named chat rooms
- Real-time bidirectional messaging
- Message history loaded on room join
- Timestamp prefix on every message
- Emoji shortcode rendering (e.g. :smile: -> 😄)
- Desktop notification (window title flash) when a new message
  arrives while the window is not focused
- Graceful handling of disconnection notices

SECURITY NOTE: This client communicates with the server over a plain
TCP socket with NO encryption. Do not use this for sensitive
communication over an untrusted network. See server file for details.
"""

import socket
import threading
import json
import queue
import tkinter as tk
from tkinter import ttk, messagebox

HOST = "localhost"
PORT = 5555


class Theme:
    """Centralized color and font tokens for the app's visual design."""
    BG = "#161821"           # app background — deep slate
    CARD = "#1f2230"         # card surface, one step lighter than bg
    CARD_BORDER = "#2c3044"
    ACCENT = "#7c5cff"       # primary accent — violet
    ACCENT_HOVER = "#8f72ff"
    ACCENT_TEXT = "#ffffff"
    TEXT_PRIMARY = "#eef0f6"
    TEXT_MUTED = "#8b8fa3"
    INPUT_BG = "#262a3b"
    INPUT_BORDER = "#3a3f57"
    DIVIDER = "#2c3044"
    SUCCESS = "#4ade80"
    DANGER = "#f87171"
    SYSTEM_MSG = "#8b8fa3"

    FONT_FAMILY = "Segoe UI"
    FONT_BRAND = (FONT_FAMILY, 22, "bold")
    FONT_SUBTITLE = (FONT_FAMILY, 10)
    FONT_LABEL = (FONT_FAMILY, 9)
    FONT_BODY = (FONT_FAMILY, 11)
    FONT_TAB = (FONT_FAMILY, 10, "bold")
    FONT_CHAT = ("Consolas", 10)


# A small set of common emoji shortcodes -> Unicode characters
EMOJI_MAP = {
    ":smile:": "😄",
    ":laughing:": "😆",
    ":heart:": "❤️",
    ":thumbsup:": "👍",
    ":thumbsdown:": "👎",
    ":fire:": "🔥",
    ":wave:": "👋",
    ":sad:": "😢",
    ":cry:": "😭",
    ":thinking:": "🤔",
    ":party:": "🎉",
    ":ok:": "👌",
    ":clap:": "👏",
    ":eyes:": "👀",
    ":rocket:": "🚀",
}


def render_emoji_shortcodes(text):
    for code, emoji in EMOJI_MAP.items():
        text = text.replace(code, emoji)
    return text


class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Chatter")
        self.root.geometry("480x640")
        self.root.configure(bg=Theme.BG)
        self.root.minsize(420, 520)

        self.sock = None
        self.buffer = ""
        self.username = None
        self.current_room = None
        self.window_focused = True
        self.auth_mode = "login"  # or "register"
        self.incoming_queue = queue.Queue()

        self.setup_styles()

        self.root.bind("<FocusIn>", self.on_focus_in)
        self.root.bind("<FocusOut>", self.on_focus_out)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        connected = self.connect_to_server()
        if not connected:
            return  # window was already destroyed; stop initializing further

        self.build_login_screen()

        # Poll the incoming message queue regularly on the main thread
        self.root.after(100, self.process_incoming_queue)

    # ---------- Styling ----------

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Accent.TButton",
            background=Theme.ACCENT,
            foreground=Theme.ACCENT_TEXT,
            font=(Theme.FONT_FAMILY, 11, "bold"),
            padding=(10, 10),
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", Theme.ACCENT_HOVER), ("pressed", Theme.ACCENT_HOVER)],
        )

        style.configure(
            "Tab.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_MUTED,
            font=Theme.FONT_TAB,
            borderwidth=0,
            padding=(0, 10),
        )
        style.map(
            "Tab.TButton",
            background=[("active", Theme.CARD)],
            foreground=[("active", Theme.TEXT_PRIMARY)],
        )

        style.configure(
            "TabActive.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_PRIMARY,
            font=Theme.FONT_TAB,
            borderwidth=0,
            padding=(0, 10),
        )
        style.map("TabActive.TButton", background=[("active", Theme.CARD)])

        style.configure(
            "Ghost.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_MUTED,
            font=Theme.FONT_LABEL,
            borderwidth=0,
            padding=(6, 6),
        )
        style.map("Ghost.TButton", foreground=[("active", Theme.TEXT_PRIMARY)])

        style.configure(
            "Chat.TEntry",
            fieldbackground=Theme.INPUT_BG,
            background=Theme.INPUT_BG,
            foreground=Theme.TEXT_PRIMARY,
            bordercolor=Theme.INPUT_BORDER,
            lightcolor=Theme.INPUT_BORDER,
            darkcolor=Theme.INPUT_BORDER,
            insertcolor=Theme.TEXT_PRIMARY,
            borderwidth=1,
            padding=8,
        )
        style.map(
            "Chat.TEntry",
            bordercolor=[("focus", Theme.ACCENT)],
            lightcolor=[("focus", Theme.ACCENT)],
        )

    def styled_entry(self, parent, show=None):
        entry = ttk.Entry(parent, style="Chat.TEntry", font=Theme.FONT_BODY, show=show)
        return entry

    # ---------- Networking ----------

    def connect_to_server(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            listener = threading.Thread(target=self.listen_for_messages, daemon=True)
            listener.start()
            return True
        except ConnectionRefusedError:
            messagebox.showerror(
                "Connection Failed",
                f"Could not connect to server at {HOST}:{PORT}.\nMake sure chat_server.py is running.",
            )
            self.root.destroy()
            return False

    def listen_for_messages(self):
        """Runs in a background thread, reads newline-delimited JSON messages."""
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.buffer += chunk.decode("utf-8")

                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                        self.incoming_queue.put(msg)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass  # socket closed

    def send_json(self, data):
        try:
            self.sock.sendall((json.dumps(data) + "\n").encode("utf-8"))
        except OSError:
            messagebox.showerror("Connection Error", "Lost connection to the server.")

    def process_incoming_queue(self):
        """Runs on the main thread; safely updates the GUI with new messages."""
        try:
            while True:
                msg = self.incoming_queue.get_nowait()
                self.handle_server_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.process_incoming_queue)

    def handle_server_message(self, msg):
        action = msg.get("action")

        if action == "register_result":
            if msg["success"]:
                messagebox.showinfo("Registration", msg["message"] + " You can now log in.")
                self.set_auth_mode("login")
            else:
                messagebox.showerror("Registration Failed", msg["message"])

        elif action == "login_result":
            if msg["success"]:
                self.build_room_screen()
            else:
                messagebox.showerror("Login Failed", msg["message"])

        elif action == "room_history":
            self.chat_display.config(state="normal")
            self.chat_display.delete("1.0", tk.END)
            for entry in msg["history"]:
                self.append_message(entry["timestamp"], entry["username"], entry["content"])
            self.chat_display.config(state="disabled")

        elif action == "message":
            if msg["room"] == self.current_room:
                self.append_message(msg["timestamp"], msg["username"], msg["content"])
                if not self.window_focused and msg["username"] != self.username:
                    self.flash_title()

    # ---------- Focus / notification handling ----------

    def on_focus_in(self, event):
        self.window_focused = True
        self.root.title("Python Chat App")

    def on_focus_out(self, event):
        self.window_focused = False

    def flash_title(self):
        self.root.title("🔔 New message! - Python Chat App")

    def on_close(self):
        if self.sock:
            self.sock.close()
        self.root.destroy()

    # ---------- Screens ----------

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def build_login_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        # Outer wrapper centers the card both directions
        outer = tk.Frame(self.root, bg=Theme.BG)
        outer.pack(expand=True, fill="both")

        # Brand header, sits above the card
        brand = tk.Frame(outer, bg=Theme.BG)
        brand.pack(pady=(60, 24))
        tk.Label(brand, text="💬", font=(Theme.FONT_FAMILY, 32), bg=Theme.BG).pack()
        tk.Label(brand, text="Chatter", font=Theme.FONT_BRAND, bg=Theme.BG, fg=Theme.TEXT_PRIMARY).pack(pady=(4, 2))
        tk.Label(
            brand, text="Real-time messaging, kept simple.",
            font=Theme.FONT_SUBTITLE, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        ).pack()

        # Card container
        card_wrap = tk.Frame(outer, bg=Theme.CARD_BORDER)
        card_wrap.pack(padx=40)
        card = tk.Frame(card_wrap, bg=Theme.CARD, padx=1, pady=1)
        card.pack(padx=1, pady=1)
        inner = tk.Frame(card, bg=Theme.CARD, padx=28, pady=26)
        inner.pack()

        # Tab toggle between Login / Register
        tabs = tk.Frame(inner, bg=Theme.CARD)
        tabs.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        tabs.grid_columnconfigure(0, weight=1)
        tabs.grid_columnconfigure(1, weight=1)

        self.login_tab_btn = ttk.Button(
            tabs, text="Log In", style="TabActive.TButton", command=lambda: self.set_auth_mode("login")
        )
        self.login_tab_btn.grid(row=0, column=0, sticky="ew")

        self.register_tab_btn = ttk.Button(
            tabs, text="Register", style="Tab.TButton", command=lambda: self.set_auth_mode("register")
        )
        self.register_tab_btn.grid(row=0, column=1, sticky="ew")

        self.tab_underline = tk.Frame(inner, bg=Theme.ACCENT, height=2)
        self.tab_underline.grid(row=1, column=0, sticky="ew", columnspan=1)

        # Form fields
        tk.Label(
            inner, text="Username", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 4))
        self.username_entry = self.styled_entry(inner)
        self.username_entry.grid(row=3, column=0, columnspan=2, sticky="ew", ipady=4)

        tk.Label(
            inner, text="Password", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 4))
        self.password_entry = self.styled_entry(inner, show="•")
        self.password_entry.grid(row=5, column=0, columnspan=2, sticky="ew", ipady=4)
        self.password_entry.bind("<Return>", lambda event: self.handle_auth_submit())

        self.auth_submit_btn = ttk.Button(
            inner, text="Log In", style="Accent.TButton", command=self.handle_auth_submit
        )
        self.auth_submit_btn.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(22, 0))

        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        self.set_auth_mode("login")

    def set_auth_mode(self, mode):
        self.auth_mode = mode
        if mode == "login":
            self.login_tab_btn.configure(style="TabActive.TButton")
            self.register_tab_btn.configure(style="Tab.TButton")
            self.auth_submit_btn.configure(text="Log In")
            self.tab_underline.grid(row=1, column=0, sticky="ew")
        else:
            self.login_tab_btn.configure(style="Tab.TButton")
            self.register_tab_btn.configure(style="TabActive.TButton")
            self.auth_submit_btn.configure(text="Create Account")
            self.tab_underline.grid(row=1, column=1, sticky="ew")

    def handle_auth_submit(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning("Missing Info", "Please enter both username and password.")
            return

        if self.auth_mode == "login":
            self.username = username
            self.send_json({"action": "login", "username": username, "password": password})
        else:
            self.send_json({"action": "register", "username": username, "password": password})

    def build_room_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        outer = tk.Frame(self.root, bg=Theme.BG)
        outer.pack(expand=True, fill="both")

        brand = tk.Frame(outer, bg=Theme.BG)
        brand.pack(pady=(60, 24))
        tk.Label(brand, text="👋", font=(Theme.FONT_FAMILY, 32), bg=Theme.BG).pack()
        tk.Label(
            brand, text=f"Welcome, {self.username}", font=Theme.FONT_BRAND, bg=Theme.BG, fg=Theme.TEXT_PRIMARY
        ).pack(pady=(4, 2))
        tk.Label(
            brand, text="Join or create a room to start chatting.",
            font=Theme.FONT_SUBTITLE, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        ).pack()

        card_wrap = tk.Frame(outer, bg=Theme.CARD_BORDER)
        card_wrap.pack(padx=40)
        card = tk.Frame(card_wrap, bg=Theme.CARD, padx=1, pady=1)
        card.pack(padx=1, pady=1)
        inner = tk.Frame(card, bg=Theme.CARD, padx=28, pady=26)
        inner.pack()

        tk.Label(
            inner, text="Room name", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.room_entry = self.styled_entry(inner)
        self.room_entry.grid(row=1, column=0, sticky="ew", ipady=4)
        self.room_entry.insert(0, "general")
        self.room_entry.bind("<Return>", lambda event: self.handle_join_room())

        ttk.Button(
            inner, text="Join Room", style="Accent.TButton", command=self.handle_join_room
        ).grid(row=2, column=0, sticky="ew", pady=(18, 0))

        inner.grid_columnconfigure(0, minsize=260)

    def handle_join_room(self):
        room = self.room_entry.get().strip()
        if not room:
            messagebox.showwarning("Missing Info", "Please enter a room name.")
            return
        self.current_room = room
        self.send_json({"action": "join_room", "room": room})
        self.build_chat_screen()

    def build_chat_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        # Top bar
        top_bar = tk.Frame(self.root, bg=Theme.CARD, height=52)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        info = tk.Frame(top_bar, bg=Theme.CARD)
        info.pack(side="left", padx=18)
        tk.Label(
            info, text=f"#{self.current_room}", font=(Theme.FONT_FAMILY, 12, "bold"),
            bg=Theme.CARD, fg=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            info, text=f"logged in as {self.username}", font=Theme.FONT_LABEL,
            bg=Theme.CARD, fg=Theme.TEXT_MUTED,
        ).pack(anchor="w")

        divider = tk.Frame(self.root, bg=Theme.DIVIDER, height=1)
        divider.pack(fill="x")

        # Chat display
        chat_wrap = tk.Frame(self.root, bg=Theme.BG)
        chat_wrap.pack(fill="both", expand=True, padx=14, pady=12)

        self.chat_display = tk.Text(
            chat_wrap, state="disabled", wrap="word",
            bg=Theme.BG, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_CHAT,
            borderwidth=0, highlightthickness=0, padx=4, pady=4,
        )
        self.chat_display.tag_configure("username", foreground=Theme.ACCENT, font=(Theme.FONT_FAMILY, 10, "bold"))
        self.chat_display.tag_configure("timestamp", foreground=Theme.TEXT_MUTED)
        self.chat_display.tag_configure("system", foreground=Theme.SYSTEM_MSG, font=(Theme.FONT_FAMILY, 9, "italic"))
        self.chat_display.tag_configure("content", foreground=Theme.TEXT_PRIMARY)

        scrollbar = ttk.Scrollbar(chat_wrap, command=self.chat_display.yview)
        self.chat_display.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.chat_display.pack(side="left", fill="both", expand=True)

        # Bottom input bar
        bottom_bar = tk.Frame(self.root, bg=Theme.CARD, height=64)
        bottom_bar.pack(fill="x")
        bottom_bar.pack_propagate(False)

        input_wrap = tk.Frame(bottom_bar, bg=Theme.CARD)
        input_wrap.pack(fill="both", expand=True, padx=14, pady=12)

        self.message_entry = self.styled_entry(input_wrap)
        self.message_entry.pack(side="left", fill="both", expand=True, ipady=6, padx=(0, 10))
        self.message_entry.bind("<Return>", lambda event: self.send_message())
        self.message_entry.focus()

        ttk.Button(
            input_wrap, text="Send", style="Accent.TButton", command=self.send_message
        ).pack(side="right", fill="y")

        hint = tk.Label(
            self.root,
            text="Tip: try :smile: :heart: :fire: :thumbsup: :wave: :party:",
            font=Theme.FONT_LABEL, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        )
        hint.pack(pady=(0, 8))

    def send_message(self):
        content = self.message_entry.get().strip()
        if not content:
            return
        content = render_emoji_shortcodes(content)
        self.send_json({"action": "message", "content": content})
        self.message_entry.delete(0, tk.END)

    def append_message(self, timestamp, username, content):
        content = render_emoji_shortcodes(content)
        self.chat_display.config(state="normal")

        if username == "System":
            self.chat_display.insert(tk.END, f"[{timestamp}] {content}\n", "system")
        else:
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{username}", "username")
            self.chat_display.insert(tk.END, f"  {content}\n", "content")

        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")


def main():
    root = tk.Tk()
    ChatClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""
Chat Application - Client (Advanced Tier)
--------------------------------------------
A tkinter GUI client for the chat server. Supports:
- User registration and login
- Joining/creating named chat rooms
- Real-time bidirectional messaging
- Message history loaded on room join
- Timestamp prefix on every message
- Emoji shortcode rendering (e.g. :smile: -> 😄)
- Desktop notification (window title flash) when a new message
  arrives while the window is not focused
- Graceful handling of disconnection notices

SECURITY NOTE: This client communicates with the server over a plain
TCP socket with NO encryption. Do not use this for sensitive
communication over an untrusted network. See server file for details.
"""

import socket
import threading
import json
import queue
import tkinter as tk
from tkinter import ttk, messagebox

HOST = "localhost"
PORT = 5555


class Theme:
    """Centralized color and font tokens for the app's visual design."""
    BG = "#161821"           # app background — deep slate
    CARD = "#1f2230"         # card surface, one step lighter than bg
    CARD_BORDER = "#2c3044"
    ACCENT = "#7c5cff"       # primary accent — violet
    ACCENT_HOVER = "#8f72ff"
    ACCENT_TEXT = "#ffffff"
    TEXT_PRIMARY = "#eef0f6"
    TEXT_MUTED = "#8b8fa3"
    INPUT_BG = "#262a3b"
    INPUT_BORDER = "#3a3f57"
    DIVIDER = "#2c3044"
    SUCCESS = "#4ade80"
    DANGER = "#f87171"
    SYSTEM_MSG = "#8b8fa3"

    FONT_FAMILY = "Segoe UI"
    FONT_BRAND = (FONT_FAMILY, 22, "bold")
    FONT_SUBTITLE = (FONT_FAMILY, 10)
    FONT_LABEL = (FONT_FAMILY, 9)
    FONT_BODY = (FONT_FAMILY, 11)
    FONT_TAB = (FONT_FAMILY, 10, "bold")
    FONT_CHAT = ("Consolas", 10)


# A small set of common emoji shortcodes -> Unicode characters
EMOJI_MAP = {
    ":smile:": "😄",
    ":laughing:": "😆",
    ":heart:": "❤️",
    ":thumbsup:": "👍",
    ":thumbsdown:": "👎",
    ":fire:": "🔥",
    ":wave:": "👋",
    ":sad:": "😢",
    ":cry:": "😭",
    ":thinking:": "🤔",
    ":party:": "🎉",
    ":ok:": "👌",
    ":clap:": "👏",
    ":eyes:": "👀",
    ":rocket:": "🚀",
}


def render_emoji_shortcodes(text):
    for code, emoji in EMOJI_MAP.items():
        text = text.replace(code, emoji)
    return text


class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Chatter")
        self.root.geometry("480x640")
        self.root.configure(bg=Theme.BG)
        self.root.minsize(420, 520)

        self.sock = None
        self.buffer = ""
        self.username = None
        self.current_room = None
        self.window_focused = True
        self.auth_mode = "login"  # or "register"
        self.incoming_queue = queue.Queue()

        self.setup_styles()

        self.root.bind("<FocusIn>", self.on_focus_in)
        self.root.bind("<FocusOut>", self.on_focus_out)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        connected = self.connect_to_server()
        if not connected:
            return  # window was already destroyed; stop initializing further

        self.build_login_screen()

        # Poll the incoming message queue regularly on the main thread
        self.root.after(100, self.process_incoming_queue)

    # ---------- Styling ----------

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Accent.TButton",
            background=Theme.ACCENT,
            foreground=Theme.ACCENT_TEXT,
            font=(Theme.FONT_FAMILY, 11, "bold"),
            padding=(10, 10),
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", Theme.ACCENT_HOVER), ("pressed", Theme.ACCENT_HOVER)],
        )

        style.configure(
            "Tab.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_MUTED,
            font=Theme.FONT_TAB,
            borderwidth=0,
            padding=(0, 10),
        )
        style.map(
            "Tab.TButton",
            background=[("active", Theme.CARD)],
            foreground=[("active", Theme.TEXT_PRIMARY)],
        )

        style.configure(
            "TabActive.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_PRIMARY,
            font=Theme.FONT_TAB,
            borderwidth=0,
            padding=(0, 10),
        )
        style.map("TabActive.TButton", background=[("active", Theme.CARD)])

        style.configure(
            "Ghost.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_MUTED,
            font=Theme.FONT_LABEL,
            borderwidth=0,
            padding=(6, 6),
        )
        style.map("Ghost.TButton", foreground=[("active", Theme.TEXT_PRIMARY)])

        style.configure(
            "Chat.TEntry",
            fieldbackground=Theme.INPUT_BG,
            background=Theme.INPUT_BG,
            foreground=Theme.TEXT_PRIMARY,
            bordercolor=Theme.INPUT_BORDER,
            lightcolor=Theme.INPUT_BORDER,
            darkcolor=Theme.INPUT_BORDER,
            insertcolor=Theme.TEXT_PRIMARY,
            borderwidth=1,
            padding=8,
        )
        style.map(
            "Chat.TEntry",
            bordercolor=[("focus", Theme.ACCENT)],
            lightcolor=[("focus", Theme.ACCENT)],
        )

    def styled_entry(self, parent, show=None):
        entry = ttk.Entry(parent, style="Chat.TEntry", font=Theme.FONT_BODY, show=show)
        return entry

    # ---------- Networking ----------

    def connect_to_server(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            listener = threading.Thread(target=self.listen_for_messages, daemon=True)
            listener.start()
            return True
        except ConnectionRefusedError:
            messagebox.showerror(
                "Connection Failed",
                f"Could not connect to server at {HOST}:{PORT}.\nMake sure chat_server.py is running.",
            )
            self.root.destroy()
            return False

    def listen_for_messages(self):
        """Runs in a background thread, reads newline-delimited JSON messages."""
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.buffer += chunk.decode("utf-8")

                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                        self.incoming_queue.put(msg)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass  # socket closed

    def send_json(self, data):
        try:
            self.sock.sendall((json.dumps(data) + "\n").encode("utf-8"))
        except OSError:
            messagebox.showerror("Connection Error", "Lost connection to the server.")

    def process_incoming_queue(self):
        """Runs on the main thread; safely updates the GUI with new messages."""
        try:
            while True:
                msg = self.incoming_queue.get_nowait()
                self.handle_server_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.process_incoming_queue)

    def handle_server_message(self, msg):
        action = msg.get("action")

        if action == "register_result":
            if msg["success"]:
                messagebox.showinfo("Registration", msg["message"] + " You can now log in.")
                self.set_auth_mode("login")
            else:
                messagebox.showerror("Registration Failed", msg["message"])

        elif action == "login_result":
            if msg["success"]:
                self.build_room_screen()
            else:
                messagebox.showerror("Login Failed", msg["message"])

        elif action == "room_history":
            self.chat_display.config(state="normal")
            self.chat_display.delete("1.0", tk.END)
            for entry in msg["history"]:
                self.append_message(entry["timestamp"], entry["username"], entry["content"])
            self.chat_display.config(state="disabled")

        elif action == "message":
            if msg["room"] == self.current_room:
                self.append_message(msg["timestamp"], msg["username"], msg["content"])
                if not self.window_focused and msg["username"] != self.username:
                    self.flash_title()

    # ---------- Focus / notification handling ----------

    def on_focus_in(self, event):
        self.window_focused = True
        self.root.title("Python Chat App")

    def on_focus_out(self, event):
        self.window_focused = False

    def flash_title(self):
        self.root.title("🔔 New message! - Python Chat App")

    def on_close(self):
        if self.sock:
            self.sock.close()
        self.root.destroy()

    # ---------- Screens ----------

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def build_login_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        # Outer wrapper centers the card both directions
        outer = tk.Frame(self.root, bg=Theme.BG)
        outer.pack(expand=True, fill="both")

        # Brand header, sits above the card
        brand = tk.Frame(outer, bg=Theme.BG)
        brand.pack(pady=(60, 24))
        tk.Label(brand, text="💬", font=(Theme.FONT_FAMILY, 32), bg=Theme.BG).pack()
        tk.Label(brand, text="Chatter", font=Theme.FONT_BRAND, bg=Theme.BG, fg=Theme.TEXT_PRIMARY).pack(pady=(4, 2))
        tk.Label(
            brand, text="Real-time messaging, kept simple.",
            font=Theme.FONT_SUBTITLE, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        ).pack()

        # Card container
        card_wrap = tk.Frame(outer, bg=Theme.CARD_BORDER)
        card_wrap.pack(padx=40)
        card = tk.Frame(card_wrap, bg=Theme.CARD, padx=1, pady=1)
        card.pack(padx=1, pady=1)
        inner = tk.Frame(card, bg=Theme.CARD, padx=28, pady=26)
        inner.pack()

        # Tab toggle between Login / Register
        tabs = tk.Frame(inner, bg=Theme.CARD)
        tabs.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        tabs.grid_columnconfigure(0, weight=1)
        tabs.grid_columnconfigure(1, weight=1)

        self.login_tab_btn = ttk.Button(
            tabs, text="Log In", style="TabActive.TButton", command=lambda: self.set_auth_mode("login")
        )
        self.login_tab_btn.grid(row=0, column=0, sticky="ew")

        self.register_tab_btn = ttk.Button(
            tabs, text="Register", style="Tab.TButton", command=lambda: self.set_auth_mode("register")
        )
        self.register_tab_btn.grid(row=0, column=1, sticky="ew")

        self.tab_underline = tk.Frame(inner, bg=Theme.ACCENT, height=2)
        self.tab_underline.grid(row=1, column=0, sticky="ew", columnspan=1)

        # Form fields
        tk.Label(
            inner, text="Username", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 4))
        self.username_entry = self.styled_entry(inner)
        self.username_entry.grid(row=3, column=0, columnspan=2, sticky="ew", ipady=4)

        tk.Label(
            inner, text="Password", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 4))
        self.password_entry = self.styled_entry(inner, show="•")
        self.password_entry.grid(row=5, column=0, columnspan=2, sticky="ew", ipady=4)
        self.password_entry.bind("<Return>", lambda event: self.handle_auth_submit())

        self.auth_submit_btn = ttk.Button(
            inner, text="Log In", style="Accent.TButton", command=self.handle_auth_submit
        )
        self.auth_submit_btn.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(22, 0))

        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        self.set_auth_mode("login")

    def set_auth_mode(self, mode):
        self.auth_mode = mode
        if mode == "login":
            self.login_tab_btn.configure(style="TabActive.TButton")
            self.register_tab_btn.configure(style="Tab.TButton")
            self.auth_submit_btn.configure(text="Log In")
            self.tab_underline.grid(row=1, column=0, sticky="ew")
        else:
            self.login_tab_btn.configure(style="Tab.TButton")
            self.register_tab_btn.configure(style="TabActive.TButton")
            self.auth_submit_btn.configure(text="Create Account")
            self.tab_underline.grid(row=1, column=1, sticky="ew")

    def handle_auth_submit(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning("Missing Info", "Please enter both username and password.")
            return

        if self.auth_mode == "login":
            self.username = username
            self.send_json({"action": "login", "username": username, "password": password})
        else:
            self.send_json({"action": "register", "username": username, "password": password})

    def build_room_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        outer = tk.Frame(self.root, bg=Theme.BG)
        outer.pack(expand=True, fill="both")

        brand = tk.Frame(outer, bg=Theme.BG)
        brand.pack(pady=(60, 24))
        tk.Label(brand, text="👋", font=(Theme.FONT_FAMILY, 32), bg=Theme.BG).pack()
        tk.Label(
            brand, text=f"Welcome, {self.username}", font=Theme.FONT_BRAND, bg=Theme.BG, fg=Theme.TEXT_PRIMARY
        ).pack(pady=(4, 2))
        tk.Label(
            brand, text="Join or create a room to start chatting.",
            font=Theme.FONT_SUBTITLE, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        ).pack()

        card_wrap = tk.Frame(outer, bg=Theme.CARD_BORDER)
        card_wrap.pack(padx=40)
        card = tk.Frame(card_wrap, bg=Theme.CARD, padx=1, pady=1)
        card.pack(padx=1, pady=1)
        inner = tk.Frame(card, bg=Theme.CARD, padx=28, pady=26)
        inner.pack()

        tk.Label(
            inner, text="Room name", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.room_entry = self.styled_entry(inner)
        self.room_entry.grid(row=1, column=0, sticky="ew", ipady=4)
        self.room_entry.insert(0, "general")
        self.room_entry.bind("<Return>", lambda event: self.handle_join_room())

        ttk.Button(
            inner, text="Join Room", style="Accent.TButton", command=self.handle_join_room
        ).grid(row=2, column=0, sticky="ew", pady=(18, 0))

        inner.grid_columnconfigure(0, minsize=260)

    def handle_join_room(self):
        room = self.room_entry.get().strip()
        if not room:
            messagebox.showwarning("Missing Info", "Please enter a room name.")
            return
        self.current_room = room
        self.send_json({"action": "join_room", "room": room})
        self.build_chat_screen()

    def build_chat_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        # Top bar
        top_bar = tk.Frame(self.root, bg=Theme.CARD, height=52)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        info = tk.Frame(top_bar, bg=Theme.CARD)
        info.pack(side="left", padx=18)
        tk.Label(
            info, text=f"#{self.current_room}", font=(Theme.FONT_FAMILY, 12, "bold"),
            bg=Theme.CARD, fg=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            info, text=f"logged in as {self.username}", font=Theme.FONT_LABEL,
            bg=Theme.CARD, fg=Theme.TEXT_MUTED,
        ).pack(anchor="w")

        divider = tk.Frame(self.root, bg=Theme.DIVIDER, height=1)
        divider.pack(fill="x")

        # Chat display
        chat_wrap = tk.Frame(self.root, bg=Theme.BG)
        chat_wrap.pack(fill="both", expand=True, padx=14, pady=12)

        self.chat_display = tk.Text(
            chat_wrap, state="disabled", wrap="word",
            bg=Theme.BG, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_CHAT,
            borderwidth=0, highlightthickness=0, padx=4, pady=4,
        )
        self.chat_display.tag_configure("username", foreground=Theme.ACCENT, font=(Theme.FONT_FAMILY, 10, "bold"))
        self.chat_display.tag_configure("timestamp", foreground=Theme.TEXT_MUTED)
        self.chat_display.tag_configure("system", foreground=Theme.SYSTEM_MSG, font=(Theme.FONT_FAMILY, 9, "italic"))
        self.chat_display.tag_configure("content", foreground=Theme.TEXT_PRIMARY)

        scrollbar = ttk.Scrollbar(chat_wrap, command=self.chat_display.yview)
        self.chat_display.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.chat_display.pack(side="left", fill="both", expand=True)

        # Bottom input bar
        bottom_bar = tk.Frame(self.root, bg=Theme.CARD, height=64)
        bottom_bar.pack(fill="x")
        bottom_bar.pack_propagate(False)

        input_wrap = tk.Frame(bottom_bar, bg=Theme.CARD)
        input_wrap.pack(fill="both", expand=True, padx=14, pady=12)

        self.message_entry = self.styled_entry(input_wrap)
        self.message_entry.pack(side="left", fill="both", expand=True, ipady=6, padx=(0, 10))
        self.message_entry.bind("<Return>", lambda event: self.send_message())
        self.message_entry.focus()

        ttk.Button(
            input_wrap, text="Send", style="Accent.TButton", command=self.send_message
        ).pack(side="right", fill="y")

        hint = tk.Label(
            self.root,
            text="Tip: try :smile: :heart: :fire: :thumbsup: :wave: :party:",
            font=Theme.FONT_LABEL, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        )
        hint.pack(pady=(0, 8))

    def send_message(self):
        content = self.message_entry.get().strip()
        if not content:
            return
        content = render_emoji_shortcodes(content)
        self.send_json({"action": "message", "content": content})
        self.message_entry.delete(0, tk.END)

    def append_message(self, timestamp, username, content):
        content = render_emoji_shortcodes(content)
        self.chat_display.config(state="normal")

        if username == "System":
            self.chat_display.insert(tk.END, f"[{timestamp}] {content}\n", "system")
        else:
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{username}", "username")
            self.chat_display.insert(tk.END, f"  {content}\n", "content")

        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")


def main():
    root = tk.Tk()
    ChatClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""
Chat Application - Client (Advanced Tier)
--------------------------------------------
A tkinter GUI client for the chat server. Supports:
- User registration and login
- Joining/creating named chat rooms
- Real-time bidirectional messaging
- Message history loaded on room join
- Timestamp prefix on every message
- Emoji shortcode rendering (e.g. :smile: -> 😄)
- Desktop notification (window title flash) when a new message
  arrives while the window is not focused
- Graceful handling of disconnection notices

SECURITY NOTE: This client communicates with the server over a plain
TCP socket with NO encryption. Do not use this for sensitive
communication over an untrusted network. See server file for details.
"""

import socket
import threading
import json
import queue
import tkinter as tk
from tkinter import ttk, messagebox

HOST = "localhost"
PORT = 5555


class Theme:
    """Centralized color and font tokens for the app's visual design."""
    BG = "#161821"           # app background — deep slate
    CARD = "#1f2230"         # card surface, one step lighter than bg
    CARD_BORDER = "#2c3044"
    ACCENT = "#7c5cff"       # primary accent — violet
    ACCENT_HOVER = "#8f72ff"
    ACCENT_TEXT = "#ffffff"
    TEXT_PRIMARY = "#eef0f6"
    TEXT_MUTED = "#8b8fa3"
    INPUT_BG = "#262a3b"
    INPUT_BORDER = "#3a3f57"
    DIVIDER = "#2c3044"
    SUCCESS = "#4ade80"
    DANGER = "#f87171"
    SYSTEM_MSG = "#8b8fa3"

    FONT_FAMILY = "Segoe UI"
    FONT_BRAND = (FONT_FAMILY, 22, "bold")
    FONT_SUBTITLE = (FONT_FAMILY, 10)
    FONT_LABEL = (FONT_FAMILY, 9)
    FONT_BODY = (FONT_FAMILY, 11)
    FONT_TAB = (FONT_FAMILY, 10, "bold")
    FONT_CHAT = ("Consolas", 10)


# A small set of common emoji shortcodes -> Unicode characters
EMOJI_MAP = {
    ":smile:": "😄",
    ":laughing:": "😆",
    ":heart:": "❤️",
    ":thumbsup:": "👍",
    ":thumbsdown:": "👎",
    ":fire:": "🔥",
    ":wave:": "👋",
    ":sad:": "😢",
    ":cry:": "😭",
    ":thinking:": "🤔",
    ":party:": "🎉",
    ":ok:": "👌",
    ":clap:": "👏",
    ":eyes:": "👀",
    ":rocket:": "🚀",
}


def render_emoji_shortcodes(text):
    for code, emoji in EMOJI_MAP.items():
        text = text.replace(code, emoji)
    return text


class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Chatter")
        self.root.geometry("480x640")
        self.root.configure(bg=Theme.BG)
        self.root.minsize(420, 520)

        self.sock = None
        self.buffer = ""
        self.username = None
        self.current_room = None
        self.window_focused = True
        self.auth_mode = "login"  # or "register"
        self.incoming_queue = queue.Queue()

        self.setup_styles()

        self.root.bind("<FocusIn>", self.on_focus_in)
        self.root.bind("<FocusOut>", self.on_focus_out)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.connect_to_server()
        self.build_login_screen()

        # Poll the incoming message queue regularly on the main thread
        self.root.after(100, self.process_incoming_queue)

    # ---------- Styling ----------

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Accent.TButton",
            background=Theme.ACCENT,
            foreground=Theme.ACCENT_TEXT,
            font=(Theme.FONT_FAMILY, 11, "bold"),
            padding=(10, 10),
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", Theme.ACCENT_HOVER), ("pressed", Theme.ACCENT_HOVER)],
        )

        style.configure(
            "Tab.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_MUTED,
            font=Theme.FONT_TAB,
            borderwidth=0,
            padding=(0, 10),
        )
        style.map(
            "Tab.TButton",
            background=[("active", Theme.CARD)],
            foreground=[("active", Theme.TEXT_PRIMARY)],
        )

        style.configure(
            "TabActive.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_PRIMARY,
            font=Theme.FONT_TAB,
            borderwidth=0,
            padding=(0, 10),
        )
        style.map("TabActive.TButton", background=[("active", Theme.CARD)])

        style.configure(
            "Ghost.TButton",
            background=Theme.CARD,
            foreground=Theme.TEXT_MUTED,
            font=Theme.FONT_LABEL,
            borderwidth=0,
            padding=(6, 6),
        )
        style.map("Ghost.TButton", foreground=[("active", Theme.TEXT_PRIMARY)])

        style.configure(
            "Chat.TEntry",
            fieldbackground=Theme.INPUT_BG,
            background=Theme.INPUT_BG,
            foreground=Theme.TEXT_PRIMARY,
            bordercolor=Theme.INPUT_BORDER,
            lightcolor=Theme.INPUT_BORDER,
            darkcolor=Theme.INPUT_BORDER,
            insertcolor=Theme.TEXT_PRIMARY,
            borderwidth=1,
            padding=8,
        )
        style.map(
            "Chat.TEntry",
            bordercolor=[("focus", Theme.ACCENT)],
            lightcolor=[("focus", Theme.ACCENT)],
        )

    def styled_entry(self, parent, show=None):
        entry = ttk.Entry(parent, style="Chat.TEntry", font=Theme.FONT_BODY, show=show)
        return entry

    # ---------- Networking ----------

    def connect_to_server(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            listener = threading.Thread(target=self.listen_for_messages, daemon=True)
            listener.start()
        except ConnectionRefusedError:
            messagebox.showerror(
                "Connection Failed",
                f"Could not connect to server at {HOST}:{PORT}.\nMake sure chat_server.py is running.",
            )
            self.root.destroy()

    def listen_for_messages(self):
        """Runs in a background thread, reads newline-delimited JSON messages."""
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.buffer += chunk.decode("utf-8")

                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                        self.incoming_queue.put(msg)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass  # socket closed

    def send_json(self, data):
        try:
            self.sock.sendall((json.dumps(data) + "\n").encode("utf-8"))
        except OSError:
            messagebox.showerror("Connection Error", "Lost connection to the server.")

    def process_incoming_queue(self):
        """Runs on the main thread; safely updates the GUI with new messages."""
        try:
            while True:
                msg = self.incoming_queue.get_nowait()
                self.handle_server_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.process_incoming_queue)

    def handle_server_message(self, msg):
        action = msg.get("action")

        if action == "register_result":
            if msg["success"]:
                messagebox.showinfo("Registration", msg["message"] + " You can now log in.")
                self.set_auth_mode("login")
            else:
                messagebox.showerror("Registration Failed", msg["message"])

        elif action == "login_result":
            if msg["success"]:
                self.build_room_screen()
            else:
                messagebox.showerror("Login Failed", msg["message"])

        elif action == "room_history":
            self.chat_display.config(state="normal")
            self.chat_display.delete("1.0", tk.END)
            for entry in msg["history"]:
                self.append_message(entry["timestamp"], entry["username"], entry["content"])
            self.chat_display.config(state="disabled")

        elif action == "message":
            if msg["room"] == self.current_room:
                self.append_message(msg["timestamp"], msg["username"], msg["content"])
                if not self.window_focused and msg["username"] != self.username:
                    self.flash_title()

    # ---------- Focus / notification handling ----------

    def on_focus_in(self, event):
        self.window_focused = True
        self.root.title("Python Chat App")

    def on_focus_out(self, event):
        self.window_focused = False

    def flash_title(self):
        self.root.title("🔔 New message! - Python Chat App")

    def on_close(self):
        if self.sock:
            self.sock.close()
        self.root.destroy()

    # ---------- Screens ----------

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def build_login_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        # Outer wrapper centers the card both directions
        outer = tk.Frame(self.root, bg=Theme.BG)
        outer.pack(expand=True, fill="both")

        # Brand header, sits above the card
        brand = tk.Frame(outer, bg=Theme.BG)
        brand.pack(pady=(60, 24))
        tk.Label(brand, text="💬", font=(Theme.FONT_FAMILY, 32), bg=Theme.BG).pack()
        tk.Label(brand, text="Chatter", font=Theme.FONT_BRAND, bg=Theme.BG, fg=Theme.TEXT_PRIMARY).pack(pady=(4, 2))
        tk.Label(
            brand, text="Real-time messaging, kept simple.",
            font=Theme.FONT_SUBTITLE, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        ).pack()

        # Card container
        card_wrap = tk.Frame(outer, bg=Theme.CARD_BORDER)
        card_wrap.pack(padx=40)
        card = tk.Frame(card_wrap, bg=Theme.CARD, padx=1, pady=1)
        card.pack(padx=1, pady=1)
        inner = tk.Frame(card, bg=Theme.CARD, padx=28, pady=26)
        inner.pack()

        # Tab toggle between Login / Register
        tabs = tk.Frame(inner, bg=Theme.CARD)
        tabs.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        tabs.grid_columnconfigure(0, weight=1)
        tabs.grid_columnconfigure(1, weight=1)

        self.login_tab_btn = ttk.Button(
            tabs, text="Log In", style="TabActive.TButton", command=lambda: self.set_auth_mode("login")
        )
        self.login_tab_btn.grid(row=0, column=0, sticky="ew")

        self.register_tab_btn = ttk.Button(
            tabs, text="Register", style="Tab.TButton", command=lambda: self.set_auth_mode("register")
        )
        self.register_tab_btn.grid(row=0, column=1, sticky="ew")

        self.tab_underline = tk.Frame(inner, bg=Theme.ACCENT, height=2)
        self.tab_underline.grid(row=1, column=0, sticky="ew", columnspan=1)

        # Form fields
        tk.Label(
            inner, text="Username", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 4))
        self.username_entry = self.styled_entry(inner)
        self.username_entry.grid(row=3, column=0, columnspan=2, sticky="ew", ipady=4)

        tk.Label(
            inner, text="Password", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 4))
        self.password_entry = self.styled_entry(inner, show="•")
        self.password_entry.grid(row=5, column=0, columnspan=2, sticky="ew", ipady=4)
        self.password_entry.bind("<Return>", lambda event: self.handle_auth_submit())

        self.auth_submit_btn = ttk.Button(
            inner, text="Log In", style="Accent.TButton", command=self.handle_auth_submit
        )
        self.auth_submit_btn.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(22, 0))

        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        self.set_auth_mode("login")

    def set_auth_mode(self, mode):
        self.auth_mode = mode
        if mode == "login":
            self.login_tab_btn.configure(style="TabActive.TButton")
            self.register_tab_btn.configure(style="Tab.TButton")
            self.auth_submit_btn.configure(text="Log In")
            self.tab_underline.grid(row=1, column=0, sticky="ew")
        else:
            self.login_tab_btn.configure(style="Tab.TButton")
            self.register_tab_btn.configure(style="TabActive.TButton")
            self.auth_submit_btn.configure(text="Create Account")
            self.tab_underline.grid(row=1, column=1, sticky="ew")

    def handle_auth_submit(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            messagebox.showwarning("Missing Info", "Please enter both username and password.")
            return

        if self.auth_mode == "login":
            self.username = username
            self.send_json({"action": "login", "username": username, "password": password})
        else:
            self.send_json({"action": "register", "username": username, "password": password})

    def build_room_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        outer = tk.Frame(self.root, bg=Theme.BG)
        outer.pack(expand=True, fill="both")

        brand = tk.Frame(outer, bg=Theme.BG)
        brand.pack(pady=(60, 24))
        tk.Label(brand, text="👋", font=(Theme.FONT_FAMILY, 32), bg=Theme.BG).pack()
        tk.Label(
            brand, text=f"Welcome, {self.username}", font=Theme.FONT_BRAND, bg=Theme.BG, fg=Theme.TEXT_PRIMARY
        ).pack(pady=(4, 2))
        tk.Label(
            brand, text="Join or create a room to start chatting.",
            font=Theme.FONT_SUBTITLE, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        ).pack()

        card_wrap = tk.Frame(outer, bg=Theme.CARD_BORDER)
        card_wrap.pack(padx=40)
        card = tk.Frame(card_wrap, bg=Theme.CARD, padx=1, pady=1)
        card.pack(padx=1, pady=1)
        inner = tk.Frame(card, bg=Theme.CARD, padx=28, pady=26)
        inner.pack()

        tk.Label(
            inner, text="Room name", font=Theme.FONT_LABEL, bg=Theme.CARD, fg=Theme.TEXT_MUTED, anchor="w"
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.room_entry = self.styled_entry(inner)
        self.room_entry.grid(row=1, column=0, sticky="ew", ipady=4)
        self.room_entry.insert(0, "general")
        self.room_entry.bind("<Return>", lambda event: self.handle_join_room())

        ttk.Button(
            inner, text="Join Room", style="Accent.TButton", command=self.handle_join_room
        ).grid(row=2, column=0, sticky="ew", pady=(18, 0))

        inner.grid_columnconfigure(0, minsize=260)

    def handle_join_room(self):
        room = self.room_entry.get().strip()
        if not room:
            messagebox.showwarning("Missing Info", "Please enter a room name.")
            return
        self.current_room = room
        self.send_json({"action": "join_room", "room": room})
        self.build_chat_screen()

    def build_chat_screen(self):
        self.clear_screen()
        self.root.configure(bg=Theme.BG)

        # Top bar
        top_bar = tk.Frame(self.root, bg=Theme.CARD, height=52)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        info = tk.Frame(top_bar, bg=Theme.CARD)
        info.pack(side="left", padx=18)
        tk.Label(
            info, text=f"#{self.current_room}", font=(Theme.FONT_FAMILY, 12, "bold"),
            bg=Theme.CARD, fg=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            info, text=f"logged in as {self.username}", font=Theme.FONT_LABEL,
            bg=Theme.CARD, fg=Theme.TEXT_MUTED,
        ).pack(anchor="w")

        divider = tk.Frame(self.root, bg=Theme.DIVIDER, height=1)
        divider.pack(fill="x")

        # Chat display
        chat_wrap = tk.Frame(self.root, bg=Theme.BG)
        chat_wrap.pack(fill="both", expand=True, padx=14, pady=12)

        self.chat_display = tk.Text(
            chat_wrap, state="disabled", wrap="word",
            bg=Theme.BG, fg=Theme.TEXT_PRIMARY, font=Theme.FONT_CHAT,
            borderwidth=0, highlightthickness=0, padx=4, pady=4,
        )
        self.chat_display.tag_configure("username", foreground=Theme.ACCENT, font=(Theme.FONT_FAMILY, 10, "bold"))
        self.chat_display.tag_configure("timestamp", foreground=Theme.TEXT_MUTED)
        self.chat_display.tag_configure("system", foreground=Theme.SYSTEM_MSG, font=(Theme.FONT_FAMILY, 9, "italic"))
        self.chat_display.tag_configure("content", foreground=Theme.TEXT_PRIMARY)

        scrollbar = ttk.Scrollbar(chat_wrap, command=self.chat_display.yview)
        self.chat_display.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.chat_display.pack(side="left", fill="both", expand=True)

        # Bottom input bar
        bottom_bar = tk.Frame(self.root, bg=Theme.CARD, height=64)
        bottom_bar.pack(fill="x")
        bottom_bar.pack_propagate(False)

        input_wrap = tk.Frame(bottom_bar, bg=Theme.CARD)
        input_wrap.pack(fill="both", expand=True, padx=14, pady=12)

        self.message_entry = self.styled_entry(input_wrap)
        self.message_entry.pack(side="left", fill="both", expand=True, ipady=6, padx=(0, 10))
        self.message_entry.bind("<Return>", lambda event: self.send_message())
        self.message_entry.focus()

        ttk.Button(
            input_wrap, text="Send", style="Accent.TButton", command=self.send_message
        ).pack(side="right", fill="y")

        hint = tk.Label(
            self.root,
            text="Tip: try :smile: :heart: :fire: :thumbsup: :wave: :party:",
            font=Theme.FONT_LABEL, bg=Theme.BG, fg=Theme.TEXT_MUTED,
        )
        hint.pack(pady=(0, 8))

    def send_message(self):
        content = self.message_entry.get().strip()
        if not content:
            return
        content = render_emoji_shortcodes(content)
        self.send_json({"action": "message", "content": content})
        self.message_entry.delete(0, tk.END)

    def append_message(self, timestamp, username, content):
        content = render_emoji_shortcodes(content)
        self.chat_display.config(state="normal")

        if username == "System":
            self.chat_display.insert(tk.END, f"[{timestamp}] {content}\n", "system")
        else:
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{username}", "username")
            self.chat_display.insert(tk.END, f"  {content}\n", "content")

        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")


def main():
    root = tk.Tk()
    ChatClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""
BMI Calculator (Beginner Tier - Command Line)
------------------------------------------------
Prompts the user for weight (kg) and height (m), calculates BMI,
classifies it, and validates all input.
"""


def get_positive_float(prompt):
    """
    Keeps asking the user for input until they provide a valid
    positive number. Rejects non-numeric and negative/zero values.
    """
    while True:
        raw_value = input(prompt).strip()
        try:
            value = float(raw_value)
        except ValueError:
            print("  -> Invalid input. Please enter a numeric value (e.g. 65.5).")
            continue

        if value <= 0:
            print("  -> Invalid input. Value must be greater than zero.")
            continue

        return value


def calculate_bmi(weight_kg, height_m):
    """BMI = weight (kg) / height (m) squared"""
    return weight_kg / (height_m ** 2)


def classify_bmi(bmi):
    """Classifies BMI into standard health categories."""
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal"
    elif bmi < 30:
        return "Overweight"
    else:
        return "Obese"


def main():
    print("=" * 40)
    print("        BMI CALCULATOR")
    print("=" * 40)

    weight = get_positive_float("Enter your weight in kg: ")
    height = get_positive_float("Enter your height in m (e.g. 1.75): ")

    bmi = calculate_bmi(weight, height)
    category = classify_bmi(bmi)

    print("\n--- Result ---")
    print(f"Your BMI is: {bmi:.2f}")
    print(f"Category: {category}")


if __name__ == "__main__":
    while True:
        main()
        again = input("\nCalculate another BMI? (y/n): ").strip().lower()
        if again != "y":
            print("Goodbye!")
            break
        print()

"""
BMI Calculator (Beginner Tier - Command Line) - Creative Edition
------------------------------------------------------------------
Prompts the user for weight (kg) and height (m), calculates BMI,
classifies it, validates input, and adds some visual flair:
colored output, a BMI scale bar, health tips, and session history.
"""

# ANSI color codes for terminal styling
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    GRAY = "\033[90m"


CATEGORY_INFO = {
    "Underweight": {
        "color": Colors.BLUE,
        "emoji": "📉",
        "tip": "Consider a nutrient-rich diet with more calories and consult a doctor if needed.",
    },
    "Normal": {
        "color": Colors.GREEN,
        "emoji": "✅",
        "tip": "Great job! Keep up a balanced diet and regular exercise.",
    },
    "Overweight": {
        "color": Colors.YELLOW,
        "emoji": "⚠️",
        "tip": "Try incorporating more physical activity and mindful eating into your routine.",
    },
    "Obese": {
        "color": Colors.RED,
        "emoji": "🚨",
        "tip": "Consider consulting a healthcare provider for a personalized health plan.",
    },
}

# Session history (not persisted to disk, just for this run)
history = []


def print_banner():
    print(Colors.CYAN + Colors.BOLD + "=" * 46)
    print("        🧮  BMI CALCULATOR  🧮")
    print("=" * 46 + Colors.RESET)


def get_positive_float(prompt):
    """
    Keeps asking the user for input until they provide a valid
    positive number. Rejects non-numeric and negative/zero values.
    """
    while True:
        raw_value = input(Colors.CYAN + prompt + Colors.RESET).strip()
        try:
            value = float(raw_value)
        except ValueError:
            print(Colors.RED + "  -> Invalid input. Please enter a numeric value (e.g. 65.5)." + Colors.RESET)
            continue

        if value <= 0:
            print(Colors.RED + "  -> Invalid input. Value must be greater than zero." + Colors.RESET)
            continue

        return value


def calculate_bmi(weight_kg, height_m):
    """BMI = weight (kg) / height (m) squared"""
    return weight_kg / (height_m ** 2)


def classify_bmi(bmi):
    """Classifies BMI into standard health categories."""
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal"
    elif bmi < 30:
        return "Overweight"
    else:
        return "Obese"


def draw_bmi_scale(bmi):
    """
    Draws a simple visual scale bar from 10 to 40 BMI,
    with a marker showing where the user's BMI falls.
    """
    scale_min, scale_max = 10, 40
    bar_length = 40

    clamped = max(scale_min, min(bmi, scale_max))
    position = int((clamped - scale_min) / (scale_max - scale_min) * bar_length)

    bar = ""
    zone_bounds = [18.5, 25, 30]
    zone_colors = [Colors.BLUE, Colors.GREEN, Colors.YELLOW, Colors.RED]

    for i in range(bar_length):
        value_at_i = scale_min + (i / bar_length) * (scale_max - scale_min)
        if value_at_i < zone_bounds[0]:
            color = zone_colors[0]
        elif value_at_i < zone_bounds[1]:
            color = zone_colors[1]
        elif value_at_i < zone_bounds[2]:
            color = zone_colors[2]
        else:
            color = zone_colors[3]

        if i == position:
            bar += Colors.BOLD + "▲" + Colors.RESET
        else:
            bar += color + "█" + Colors.RESET

    print(f"\n  {scale_min}" + " " * (bar_length - 6) + f"{scale_max}")
    print("  " + bar)
    print(f"  {Colors.GRAY}(marker ▲ shows your BMI position on the scale){Colors.RESET}")


def show_history():
    if not history:
        return
    print(f"\n{Colors.GRAY}--- Session History ---{Colors.RESET}")
    for i, (bmi, category) in enumerate(history, start=1):
        color = CATEGORY_INFO[category]["color"]
        print(f"  {i}. BMI {bmi:.2f} -> {color}{category}{Colors.RESET}")


def main():
    print_banner()

    weight = get_positive_float("Enter your weight in kg: ")
    height = get_positive_float("Enter your height in m (e.g. 1.75): ")

    bmi = calculate_bmi(weight, height)
    category = classify_bmi(bmi)
    info = CATEGORY_INFO[category]

    history.append((bmi, category))

    print(f"\n{Colors.BOLD}--- Result ---{Colors.RESET}")
    print(f"Your BMI is: {Colors.BOLD}{bmi:.2f}{Colors.RESET}")
    print(f"Category: {info['color']}{info['emoji']} {category}{Colors.RESET}")
    print(f"{Colors.GRAY}Tip: {info['tip']}{Colors.RESET}")

    draw_bmi_scale(bmi)
    show_history()


if __name__ == "__main__":
    while True:
        main()
        again = input(f"\n{Colors.CYAN}Calculate another BMI? (y/n): {Colors.RESET}").strip().lower()
        if again != "y":
            print(Colors.BOLD + "\nThanks for using the BMI Calculator. Stay healthy! 👋" + Colors.RESET)
            break
        print()
