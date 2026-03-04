import base64
import json
import os
import queue
import socket
import struct
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from cryptography.fernet import Fernet


def derive_fernet_key(secret: str) -> bytes:
    raw = secret.encode("utf-8")
    padded = (raw * ((32 // len(raw)) + 1))[:32] if raw else b"default-secret-chat-key-32-bytes!!"
    return base64.urlsafe_b64encode(padded)


def send_packet(sock: socket.socket, data: bytes) -> None:
    sock.sendall(struct.pack("!I", len(data)) + data)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    buf = b""
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise ConnectionError("Connexion fermée.")
        buf += chunk
    return buf


def recv_packet(sock: socket.socket) -> bytes:
    header = recv_exact(sock, 4)
    (size,) = struct.unpack("!I", header)
    return recv_exact(sock, size)


class ChatClientApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NOVA Chat - Poste Client")
        self.root.geometry("1220x780")
        self.root.minsize(900, 600)

        secret = os.getenv("CHAT_SECRET", "changez-moi-rapidement-123456789")
        self.cipher = Fernet(derive_fernet_key(secret))

        self.sock = None
        self.connected = False
        self.username = ""

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.IntVar(value=5000)
        self.username_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="broadcast")

        self.incoming_queue: "queue.Queue[dict]" = queue.Queue()

        self._apply_theme()
        self._build_ui()
        self.root.after(100, self._drain_incoming)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _apply_theme(self):
        # Palette claire distincte de la version d'origine.
        self.colors = {
            "bg": "#1d2633",
            "surface": "#263447",
            "surface_alt": "#31475f",
            "text": "#e8eef7",
            "text_secondary": "#aebcd0",
            "accent": "#aa44cc",  # purple accent distinct from serveur
            "accent_hover": "#9933bb",
            "success": "#39a86b",
            "danger": "#cf5a4e",
            "danger_hover": "#b24c42",
            "border": "#415872",
            "chat_bg": "#1a2432",
            "chat_text": "#dfe7f4",
            "my_message_bg": "#146c94",
            "my_message_text": "#f2f7ff",
            "other_message_bg": "#2f4258",
            "other_message_text": "#e8eef7",
            "private_message_bg": "#254a43",
            "private_message_text": "#d6f7ef",
            "group_message_bg": "#4a3a2a",
            "group_message_text": "#f5e7d6",
            "group_message_border": "#c9955f",
            "timestamp": "#9cadc4",
            "badge_offline_bg": "#3c4f66",
            "badge_online_bg": "#2d5a46",
        }

        self.root.configure(bg=self.colors["bg"])

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            ".",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=0,
        )
        style.configure("Card.TFrame", background=self.colors["surface"], borderwidth=0)
        style.configure("Header.TFrame", background=self.colors["surface_alt"], borderwidth=0)
        style.configure(
            "Title.TLabel",
            background=self.colors["surface_alt"],
            foreground=self.colors["text"],
            font=("Trebuchet MS", 17, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text_secondary"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "Accent.TButton",
            background=self.colors["accent"],
            foreground="#f2f7ff",
            borderwidth=0,
            focuscolor="none",
            font=("Segoe UI", 10, "bold"),
            padding=(16, 8),
        )
        style.map(
            "Accent.TButton",
            background=[("active", self.colors["accent_hover"]), ("disabled", self.colors["border"])],
        )
        style.configure(
            "Danger.TButton",
            background=self.colors["danger"],
            foreground="#f2f7ff",
            borderwidth=0,
            focuscolor="none",
            font=("Segoe UI", 10, "bold"),
            padding=(16, 8),
        )
        style.map("Danger.TButton", background=[("active", self.colors["danger_hover"])])
        style.configure(
            "Muted.TButton",
            background=self.colors["surface_alt"],
            foreground=self.colors["text"],
            borderwidth=1,
            focuscolor="none",
            font=("Segoe UI", 10),
            padding=(12, 8),
        )
        style.map("Muted.TButton", background=[("active", "#efe6d8")])
        style.configure("TEntry",
            fieldbackground=self.colors["surface_alt"],
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            borderwidth=0,
            focuscolor=self.colors["accent"],
            padding=(10, 8),
        )
        style.map("TEntry", fieldbackground=[("focus", self.colors["surface_alt"])])
        style.configure("TLabelframe",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            borderwidth=1,
            relief="solid",
        )
        style.configure("TLabelframe.Label",
            background=self.colors["surface"],
            foreground=self.colors["accent"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("TRadiobutton",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            focuscolor="none",
            font=("Segoe UI", 10),
        )
        style.map("TRadiobutton", background=[("active", self.colors["surface"])])

        self.listbox_bg = self.colors["surface_alt"]
        self.listbox_fg = self.colors["text"]
        self.listbox_select = self.colors["accent"]

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # Header
        header_container = ttk.Frame(self.root, style="Header.TFrame")
        header_container.grid(row=0, column=0, sticky="ew")

        header = ttk.Frame(header_container, style="Header.TFrame", padding="18 16")
        header.pack(fill=tk.X)

        title_frame = ttk.Frame(header, style="Header.TFrame")
        title_frame.pack(side=tk.LEFT)

        ttk.Label(title_frame, text="NOVA CHAT / CLIENT", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            title_frame,
            text="Messagerie sécurisée en temps réel",
            style="Subtitle.TLabel",
        ).pack(side=tk.LEFT, padx=(12, 0))

        # Status badge
        self.status_badge = tk.Label(
            header,
            text="HORS LIGNE",
            bg=self.colors["badge_offline_bg"],
            fg=self.colors["text_secondary"],
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=5,
            relief="solid",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.status_badge.pack(side=tk.RIGHT)

        self.login_frame = ttk.LabelFrame(self.root, text="Connexion au serveur", padding="20")
        self.login_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))

        login_grid = ttk.Frame(self.login_frame, style="Card.TFrame")
        login_grid.pack(fill=tk.X)
        login_grid.columnconfigure(1, weight=2)
        login_grid.columnconfigure(3, weight=1)
        login_grid.columnconfigure(5, weight=3)

        # Première ligne
        ttk.Label(login_grid, text="Adresse serveur", style="Subtitle.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        host_entry = ttk.Entry(login_grid, textvariable=self.host_var)
        host_entry.grid(row=0, column=1, padx=(0, 16), pady=5, sticky="ew")

        ttk.Label(login_grid, text="Port TCP", style="Subtitle.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=5)
        port_entry = ttk.Entry(login_grid, textvariable=self.port_var)
        port_entry.grid(row=0, column=3, padx=(0, 16), pady=5, sticky="ew")

        ttk.Label(login_grid, text="Pseudo", style="Subtitle.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=5)
        username_entry = ttk.Entry(login_grid, textvariable=self.username_var)
        username_entry.grid(row=0, column=5, pady=5, sticky="ew")

        # Boutons
        button_frame = ttk.Frame(login_grid, style="Card.TFrame")
        button_frame.grid(row=1, column=0, columnspan=6, pady=(12, 0), sticky="e")

        self.connect_btn = ttk.Button(
            button_frame,
            text="Se connecter",
            command=self.connect,
            style="Accent.TButton",
        )
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.disconnect_btn = ttk.Button(
            button_frame,
            text="Se déconnecter",
            command=self.disconnect,
            style="Danger.TButton",
        )
        self.disconnect_btn.pack(side=tk.LEFT)

        self.clear_chat_btn = ttk.Button(
            button_frame,
            text="Effacer chat",
            command=self._clear_chat,
            style="Muted.TButton",
        )
        self.clear_chat_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Zone principale avec panneaux divisés
        main_container = ttk.Frame(self.root, style="Card.TFrame")
        main_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        main_container.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)

        main_pane = ttk.Panedwindow(main_container, orient=tk.HORIZONTAL)
        main_pane.grid(row=0, column=0, sticky="nsew")

        # Panneau de gauche - Conversation
        left_panel = ttk.Frame(main_pane, style="Card.TFrame")
        chat_frame = ttk.LabelFrame(left_panel, text="Conversation", padding="16")
        chat_frame.pack(fill=tk.BOTH, expand=True)
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)

        # Zone de texte stylisée avec Canvas pour les bulles
        chat_area = ttk.Frame(chat_frame, style="Card.TFrame")
        chat_area.grid(row=0, column=0, sticky="nsew")
        chat_area.columnconfigure(0, weight=1)
        chat_area.rowconfigure(0, weight=1)

        # Canvas pour les bulles de chat
        self.canvas = tk.Canvas(
            chat_area,
            bg=self.colors["chat_bg"],
            highlightthickness=0,
            bd=0
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Scrollbar pour le canvas
        scrollbar = ttk.Scrollbar(chat_area, command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.messages_frame = ttk.Frame(self.canvas, style="Card.TFrame")
        
        # Créer une fenêtre dans le canvas pour la frame des messages
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.messages_frame, anchor="nw")
        
        # Lier les événements
        self.messages_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Binding pour la molette de souris
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Zone d'envoi de message
        send_container = ttk.Frame(chat_frame, style="Card.TFrame")
        send_container.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        send_container.columnconfigure(0, weight=1)

        self.message_entry = ttk.Entry(send_container)
        self.message_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12), ipady=5)
        self.message_entry.bind("<Return>", lambda _: self.send_message())
        self.message_entry.configure(style="TEntry")

        self.send_btn = ttk.Button(
            send_container,
            text="Envoyer",
            command=self.send_message,
            style="Accent.TButton",
        )
        self.send_btn.grid(row=0, column=1, sticky="e")

        # Panneau de droite - Routage
        right_panel = ttk.Frame(main_pane, style="Card.TFrame")
        routing_frame = ttk.LabelFrame(right_panel, text="Distribution des messages", padding="16")
        routing_frame.pack(fill=tk.BOTH, expand=True)
        routing_frame.columnconfigure(0, weight=1)
        routing_frame.rowconfigure(3, weight=1)

        # Options de routage
        modes_frame = ttk.Frame(routing_frame, style="Card.TFrame")
        modes_frame.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        ttk.Radiobutton(
            modes_frame,
            text="Diffusion générale",
            variable=self.mode_var,
            value="broadcast",
            style="TRadiobutton",
        ).pack(anchor="w", pady=2)
        ttk.Radiobutton(
            modes_frame,
            text="Message privé",
            variable=self.mode_var,
            value="private",
            style="TRadiobutton",
        ).pack(anchor="w", pady=2)
        ttk.Radiobutton(
            modes_frame,
            text="Groupe",
            variable=self.mode_var,
            value="group",
            style="TRadiobutton",
        ).pack(anchor="w", pady=2)

        # Séparateur
        separator = tk.Frame(routing_frame, height=1, bg=self.colors["border"])
        separator.grid(row=1, column=0, sticky="ew", pady=12)

        # Liste des clients
        client_header = ttk.Frame(routing_frame, style="Card.TFrame")
        client_header.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(
            client_header,
            text="Destinataires disponibles",
            style="Subtitle.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT)

        self.client_count = ttk.Label(client_header, text="(0)", style="Subtitle.TLabel")
        self.client_count.pack(side=tk.LEFT, padx=(4, 0))

        # Listbox stylisée
        listbox_area = ttk.Frame(routing_frame, style="Card.TFrame")
        listbox_area.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        listbox_area.columnconfigure(0, weight=1)
        listbox_area.rowconfigure(0, weight=1)

        self.targets_listbox = tk.Listbox(
            listbox_area,
            selectmode=tk.MULTIPLE,
            bg=self.colors["surface_alt"],
            fg=self.colors["text"],
            selectbackground=self.colors["accent"],
            selectforeground="#f2f7ff",
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            borderwidth=0,
            font=("Segoe UI", 10),
            activestyle="none",
            relief="flat",
        )
        self.targets_listbox.grid(row=0, column=0, sticky="nsew")

        listbox_scroll = ttk.Scrollbar(listbox_area, command=self.targets_listbox.yview)
        listbox_scroll.grid(row=0, column=1, sticky="ns")
        self.targets_listbox.config(yscrollcommand=listbox_scroll.set)

        # Instructions
        ttk.Label(
            routing_frame,
            text="Mode privé: 1 cible\nMode groupe: au moins 2 cibles",
            style="Subtitle.TLabel",
            justify=tk.LEFT,
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        main_pane.add(left_panel, weight=4)
        main_pane.add(right_panel, weight=2)

    def _on_frame_configure(self, event):
        """Redimensionner le canvas quand la frame des messages change"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Ajuster la largeur de la frame des messages quand le canvas est redimensionné"""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def _on_mousewheel(self, event):
        """Gérer la molette de souris pour le scroll"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _create_message_bubble(self, text, sender, timestamp, is_me, mode="broadcast"):
        """Créer une bulle de message dans la frame des messages"""
        
        # Frame principale pour le message
        message_container = ttk.Frame(self.messages_frame, style="Card.TFrame")
        message_container.pack(fill=tk.X, pady=(0, 8))
        
        # Frame pour la bulle (avec alignement)
        bubble_frame = ttk.Frame(message_container, style="Card.TFrame")
        
        if is_me:
            bubble_frame.pack(side=tk.RIGHT, padx=(50, 10), anchor="e")
        else:
            bubble_frame.pack(side=tk.LEFT, padx=(10, 50), anchor="w")
        
        # Header de la bulle (nom et timestamp)
        header_frame = ttk.Frame(bubble_frame, style="Card.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 2))
        
        # Icône et libellé selon le mode
        mode_icons = {
            "broadcast": "📢",
            "private": "🔒",
            "group": "👥",
            "system": "ℹ️",
            "error": "❌"
        }
        mode_labels = {
            "broadcast": "Broadcast",
            "private": "Privé",
            "group": "Groupe",
            "system": "Système",
            "error": "Erreur"
        }
        icon = mode_icons.get(mode, "💬")
        mode_label = mode_labels.get(mode, "Message")
        
        # Nom de l'expéditeur avec icône
        name_label = tk.Label(
            header_frame,
            text=f"{icon} {sender} · {mode_label}",
            bg=self.colors["surface"],
            fg=self.colors["accent"],
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
        name_label.pack(side=tk.LEFT, padx=(0, 8))
        
        # Timestamp
        time_label = tk.Label(
            header_frame,
            text=timestamp,
            bg=self.colors["surface"],
            fg=self.colors["timestamp"],
            font=("Segoe UI", 8)
        )
        time_label.pack(side=tk.RIGHT)
        
        # Corps du message (bulle)
        border_color = None
        if mode == "group":
            bubble_bg = self.colors["group_message_bg"]
            bubble_fg = self.colors["group_message_text"]
            border_color = self.colors["group_message_border"]
        elif is_me:
            bubble_bg = self.colors["my_message_bg"]
            bubble_fg = self.colors["my_message_text"]
        else:
            if mode == "private":
                bubble_bg = self.colors["private_message_bg"]
                bubble_fg = self.colors["private_message_text"]
            else:
                bubble_bg = self.colors["other_message_bg"]
                bubble_fg = self.colors["other_message_text"]
        
        # Créer un Label pour le message avec wrapping
        message_label = tk.Label(
            bubble_frame,
            text=text,
            bg=bubble_bg,
            fg=bubble_fg,
            font=("Segoe UI", 10),
            wraplength=400,  # Largeur maximale avant wrap
            justify=tk.LEFT,
            padx=12,
            pady=8,
            highlightthickness=1 if border_color else 0,
            highlightbackground=border_color if border_color else bubble_bg,
            highlightcolor=border_color if border_color else bubble_bg
        )
        message_label.pack(fill=tk.X, pady=(0, 2))
        
        # Mettre à jour la frame pour forcer le redimensionnement
        self.messages_frame.update_idletasks()

    def _clear_chat(self):
        for widget in self.messages_frame.winfo_children():
            widget.destroy()

    def _update_client_count(self):
        count = self.targets_listbox.size()
        self.client_count.config(text=f"({count})")

    def _encrypt_payload(self, payload: dict) -> bytes:
        raw = json.dumps(payload).encode("utf-8")
        return self.cipher.encrypt(raw)

    def _send_payload(self, payload: dict):
        if not self.connected or not self.sock:
            raise ConnectionError("Client non connecté.")
        send_packet(self.sock, self._encrypt_payload(payload))

    def connect(self):
        if self.connected:
            return

        host = self.host_var.get().strip()
        port = self.port_var.get()
        username = self.username_var.get().strip()
        
        if not username:
            messagebox.showerror("Erreur", "Veuillez entrer un nom d'utilisateur.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, int(port)))

            send_packet(self.sock, self._encrypt_payload({"type": "auth", "username": username}))
            auth_reply = json.loads(self.cipher.decrypt(recv_packet(self.sock)).decode("utf-8"))

            if auth_reply.get("type") == "auth_ok":
                self.connected = True
                self.username = username
                
                # Mise à jour UI
                self.status_badge.config(
                    text="CONNECTÉ",
                    fg=self.colors["success"],
                    bg=self.colors["badge_online_bg"],
                    highlightbackground="#b8d4c0",
                )
                self._create_message_bubble(
                    f"Connecté en tant que {username}",
                    "Système",
                    datetime.now().strftime("%H:%M"),
                    False,
                    "system"
                )
                
                threading.Thread(target=self._recv_loop, daemon=True).start()
            else:
                msg = auth_reply.get("message", "Authentification refusée.")
                self.sock.close()
                self.sock = None
                messagebox.showerror("Erreur", msg)
        except Exception as exc:
            messagebox.showerror("Erreur de connexion", str(exc))
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

    def disconnect(self):
        if not self.connected:
            return
        self.connected = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        self.status_badge.config(
            text="HORS LIGNE",
            fg=self.colors["text_secondary"],
            bg=self.colors["badge_offline_bg"],
            highlightbackground=self.colors["border"],
        )
        self.targets_listbox.delete(0, tk.END)
        self._update_client_count()
        self._create_message_bubble(
            "Déconnecté.",
            "Système",
            datetime.now().strftime("%H:%M"),
            False,
            "system"
        )

    def _recv_loop(self):
        try:
            while self.connected and self.sock:
                packet = recv_packet(self.sock)
                data = json.loads(self.cipher.decrypt(packet).decode("utf-8"))
                self.incoming_queue.put(data)
        except Exception as exc:
            self.incoming_queue.put({"type": "system", "message": f"Connexion perdue: {exc}"})
        finally:
            self.connected = False
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

    def _drain_incoming(self):
        while not self.incoming_queue.empty():
            data = self.incoming_queue.get_nowait()
            ptype = data.get("type")

            if ptype == "chat":
                sender = data.get("sender", "?")
                mode = data.get("mode", "broadcast")
                text = data.get("message", "")
                ts = data.get("timestamp", datetime.now().strftime("%H:%M"))
                
                # Déterminer si c'est notre message
                is_me = (sender == self.username)
                
                # Créer la bulle de message
                self._create_message_bubble(text, sender, ts, is_me, mode)
                
            elif ptype == "clients":
                clients = data.get("clients", [])
                self.targets_listbox.delete(0, tk.END)
                for user in clients:
                    self.targets_listbox.insert(tk.END, user)
                self._update_client_count()
                
            elif ptype == "history":
                messages = data.get("messages", [])
                if messages:
                    self._create_message_bubble(
                        "Historique des messages",
                        "Système",
                        datetime.now().strftime("%H:%M"),
                        False,
                        "system"
                    )
                    for item in messages:
                        ts = item.get("timestamp", "")
                        sender = item.get("sender", "?")
                        mode = item.get("mode", "broadcast")
                        text = item.get("message", "")
                        is_me = (sender == self.username)
                        self._create_message_bubble(text, sender, ts, is_me, mode)
                    
            elif ptype == "error":
                self._create_message_bubble(
                    f"Erreur: {data.get('message', 'Erreur inconnue')}",
                    "Système",
                    datetime.now().strftime("%H:%M"),
                    False,
                    "error"
                )
                
            elif ptype == "system":
                self._create_message_bubble(
                    data.get('message', ''),
                    "Système",
                    datetime.now().strftime("%H:%M"),
                    False,
                    "system"
                )
                
            elif ptype == "pong":
                pass

        # Scroll automatique vers le bas
        self.canvas.yview_moveto(1.0)
        self.root.after(100, self._drain_incoming)

    def send_message(self):
        if not self.connected:
            messagebox.showwarning("Info", "Connectez-vous d'abord.")
            return

        text = self.message_entry.get().strip()
        if not text:
            return

        mode = self.mode_var.get()
        selected_indexes = self.targets_listbox.curselection()
        selected_users = [self.targets_listbox.get(i) for i in selected_indexes]

        if mode == "private" and len(selected_users) != 1:
            messagebox.showwarning("Routage", "En mode privé, sélectionnez exactement un destinataire.")
            return
            
        if mode == "group" and len(selected_users) < 2:
            messagebox.showwarning("Routage", "En mode groupé, sélectionnez au moins deux destinataires.")
            return

        payload = {
            "type": "chat",
            "mode": mode,
            "targets": selected_users,
            "message": text,
        }

        try:
            self._send_payload(payload)
            
            # Afficher le message immédiatement (optimiste)
            self._create_message_bubble(
                text,
                self.username,
                datetime.now().strftime("%H:%M"),
                True,
                mode
            )
            
            self.message_entry.delete(0, tk.END)
            
            # Scroll automatique vers le bas
            self.canvas.yview_moveto(1.0)
            
        except Exception as exc:
            messagebox.showerror("Erreur d'envoi", str(exc))

    def on_close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClientApp(root)
    root.mainloop()
