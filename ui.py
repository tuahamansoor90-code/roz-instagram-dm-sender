"""
ui.py - Full GUI for Instagram DM Sender
Built with CustomTkinter (dark purple/blue theme).
"""

import asyncio
import os
import sys
import threading
import warnings
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime

import customtkinter as ctk

import database as db
import importer as imp
from instagram_engine import InstagramEngine

# Suppress cosmetic pipe-cleanup ResourceWarnings from asyncio on Windows
warnings.filterwarnings("ignore", category=ResourceWarning)
# NOTE: Do NOT set WindowsSelectorEventLoopPolicy here.
# Playwright requires the ProactorEventLoop on Windows to launch Chromium.
# The ResourceWarning noise is suppressed above instead.

# ── Theme ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Custom palette
BG_DARK    = "#0F0F1A"
BG_CARD    = "#1A1A2E"
BG_SIDEBAR = "#12122A"
ACCENT     = "#7C3AED"        # purple
ACCENT2    = "#2563EB"        # blue
ACCENT_HOV = "#6D28D9"
TEXT_PRI   = "#F1F5F9"
TEXT_SEC   = "#94A3B8"
SUCCESS    = "#22C55E"
ERROR      = "#EF4444"
WARNING    = "#F59E0B"
BORDER     = "#2D2D4E"


# ══════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("Instagram DM Sender")
        self.geometry("1200x760")
        self.minsize(1000, 680)
        self.configure(fg_color=BG_DARK)

        # ── Persistent background event loop ──────────────────────────────
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="AsyncLoopThread"
        )
        self._loop_thread.start()

        # threading.Event — safe to set/check from any thread
        self._stop_event = threading.Event()

        # Create engine once at startup
        self._engine = InstagramEngine(log_callback=self._safe_log)
        self._campaign_future = None
        self._session_poll_id = None   # after() id for login polling

        self._build_layout()
        self._show_tab("login")
        self._refresh_contacts_table()
        self._load_template_from_db()
        self._load_settings_from_db()
        self._update_status("Ready", TEXT_SEC)

        # Clean shutdown on window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-check if a saved session already exists
        self.after(1200, self._auto_check_saved_session)

    def _on_close(self):
        """Stop the background loop gracefully then destroy the window."""
        self._stop_event.set()
        if self._session_poll_id:
            self.after_cancel(self._session_poll_id)
        if self._engine:
            asyncio.run_coroutine_threadsafe(self._engine.close(), self._loop)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self.destroy()

    def _run_async(self, coro):
        """Submit a coroutine to the persistent background loop."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _auto_check_saved_session(self):
        """On startup, silently check if a saved session exists."""
        if self._engine.has_saved_session():
            self._login_state_badge.configure(
                text="Session Found - Click Open Browser to Restore",
                text_color=WARNING,
            )
            self._update_status("Previous session found", WARNING)

    # ── Layout skeleton ────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()
        self._build_status_bar()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(10, weight=1)
        sidebar.grid_propagate(False)

        # Logo / title
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=16, pady=(24, 8), sticky="ew")

        ctk.CTkLabel(
            logo_frame, text="📸", font=ctk.CTkFont(size=32)
        ).pack(side="left")
        ctk.CTkLabel(
            logo_frame,
            text=" InstaBot",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_PRI,
        ).pack(side="left")

        ctk.CTkLabel(
            sidebar,
            text="DM Campaign Tool",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SEC,
        ).grid(row=1, column=0, padx=20, pady=(0, 20))

        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color=BORDER).grid(
            row=2, column=0, sticky="ew", padx=12
        )

        # Nav buttons
        tabs = [
            ("🔐  Login",    "login"),
            ("👥  Contacts", "contacts"),
            ("✉️  Template",  "template"),
            ("🚀  Send",     "send"),
            ("⚙️  Settings",  "settings"),
        ]
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        for row_idx, (label, key) in enumerate(tabs, start=3):
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                anchor="w",
                fg_color="transparent",
                hover_color=ACCENT,
                text_color=TEXT_SEC,
                font=ctk.CTkFont(size=14),
                height=44,
                corner_radius=10,
                command=lambda k=key: self._show_tab(k),
            )
            btn.grid(row=row_idx, column=0, padx=12, pady=3, sticky="ew")
            self._nav_buttons[key] = btn

        # Version at bottom
        ctk.CTkLabel(
            sidebar,
            text="v1.0.0  •  Instagram DM",
            font=ctk.CTkFont(size=10),
            text_color=BORDER,
        ).grid(row=20, column=0, padx=16, pady=16, sticky="s")

    def _build_main_area(self):
        self._main = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self._main.grid_columnconfigure(0, weight=1)
        self._main.grid_rowconfigure(0, weight=1)

        self._tabs: dict[str, ctk.CTkFrame] = {
            "login":    self._build_tab_login(),
            "contacts": self._build_tab_contacts(),
            "template": self._build_tab_template(),
            "send":     self._build_tab_send(),
            "settings": self._build_tab_settings(),
        }
        for frame in self._tabs.values():
            frame.grid(row=0, column=0, sticky="nsew")

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=BG_CARD, height=32, corner_radius=0)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)

        self._status_dot = ctk.CTkLabel(bar, text="●", text_color=TEXT_SEC, font=ctk.CTkFont(size=10))
        self._status_dot.pack(side="left", padx=(12, 4))
        self._status_lbl = ctk.CTkLabel(bar, text="Ready", text_color=TEXT_SEC, font=ctk.CTkFont(size=11))
        self._status_lbl.pack(side="left")

        self._time_lbl = ctk.CTkLabel(bar, text="", text_color=TEXT_SEC, font=ctk.CTkFont(size=11))
        self._time_lbl.pack(side="right", padx=12)
        self._tick_clock()

    def _tick_clock(self):
        self._time_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _update_status(self, text: str, color: str = TEXT_SEC):
        self._status_lbl.configure(text=text)
        self._status_dot.configure(text_color=color)

    # ── Tab switching ──────────────────────────────────────────────────────────

    def _show_tab(self, key: str):
        for k, frame in self._tabs.items():
            frame.tkraise() if k == key else None
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(fg_color=ACCENT, text_color=TEXT_PRI)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SEC)
        self._tabs[key].tkraise()
        if key == "contacts":
            self._refresh_contacts_table()

    # ══════════════════════════════════════════════════════════════════════════
    # LOGIN TAB  —  One-click open browser, user logs in manually
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_login(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._main, fg_color=BG_DARK)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # Centered card
        card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=24,
            border_width=1, border_color=BORDER,
        )
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.52, relheight=0.82)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.84, relheight=0.92)
        inner.grid_columnconfigure(0, weight=1)

        # Instagram icon
        ctk.CTkLabel(
            inner, text="\U0001f4f8",
            font=ctk.CTkFont(size=52),
        ).grid(row=0, column=0, pady=(0, 6))

        ctk.CTkLabel(
            inner, text="Instagram DM Sender",
            font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT_PRI,
        ).grid(row=1, column=0, pady=(0, 6))

        # Session status badge
        self._login_state_badge = ctk.CTkLabel(
            inner,
            text="Not Connected",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SEC,
        )
        self._login_state_badge.grid(row=2, column=0, pady=(0, 28))

        # ── Big open-browser button ────────────────────────────────────────
        self._open_browser_btn = ctk.CTkButton(
            inner,
            text="\U0001f310  Open Instagram in Browser",
            height=56,
            fg_color=ACCENT,
            hover_color=ACCENT_HOV,
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=14,
            command=self._do_open_browser,
        )
        self._open_browser_btn.grid(row=3, column=0, sticky="ew", pady=(0, 14))

        # How-to steps
        steps_frame = ctk.CTkFrame(inner, fg_color="#13132A", corner_radius=12)
        steps_frame.grid(row=4, column=0, sticky="ew", pady=(0, 20))

        steps = [
            ("1", "Click the button above — Chromium browser will open"),
            ("2", "Log in to Instagram normally (username/password, Google, etc.)"),
            ("3", "Complete 2FA if Instagram asks for it"),
            ("4", "Come back here — session detected automatically!"),
            ("5", "Next time: session is saved, skip login entirely"),
        ]
        for i, (num, text) in enumerate(steps):
            row_f = ctk.CTkFrame(steps_frame, fg_color="transparent")
            row_f.pack(fill="x", padx=16, pady=(10 if i == 0 else 4, 10 if i == len(steps)-1 else 4))
            ctk.CTkLabel(
                row_f,
                text=num,
                width=24, height=24,
                fg_color=ACCENT,
                corner_radius=12,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="white",
            ).pack(side="left", padx=(0, 10))
            ctk.CTkLabel(
                row_f, text=text,
                font=ctk.CTkFont(size=12), text_color=TEXT_SEC, anchor="w",
            ).pack(side="left", fill="x", expand=True)

        # Manual check button (in case auto-poll is slow)
        self._check_session_btn = ctk.CTkButton(
            inner,
            text="\u2705  I'm Logged In  —  Check Session",
            height=42,
            fg_color="#1A2E1A",
            hover_color="#1E3D1E",
            text_color=SUCCESS,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=12,
            border_color=SUCCESS,
            border_width=1,
            command=self._manual_check_session,
            state="disabled",
        )
        self._check_session_btn.grid(row=5, column=0, sticky="ew", pady=(0, 8))

        # Live status label
        self._login_status = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(size=11), text_color=TEXT_SEC,
        )
        self._login_status.grid(row=6, column=0, pady=(4, 0))

        return frame

    def _do_open_browser(self):
        """Open Chromium pointing at Instagram. Start polling for login."""
        settings = db.get_all_settings()
        browser_path = settings.get("browser_path", "")

        self._open_browser_btn.configure(state="disabled", text="Launching browser...")
        self._login_status.configure(text="Starting Chromium — please wait...", text_color=WARNING)
        self._update_status("Opening browser...", WARNING)

        async def _open_coro():
            opened_ok, already_in = await self._engine.open_browser(browser_path)
            self.after(0, lambda: self._on_browser_opened(opened_ok, already_in))

        self._run_async(_open_coro())

    def _on_browser_opened(self, opened_ok: bool, already_logged_in: bool):
        """Called after the browser open attempt completes."""
        self._open_browser_btn.configure(
            state="normal", text="\U0001f310  Open Instagram in Browser"
        )

        if not opened_ok:
            # Browser FAILED to launch
            self._login_state_badge.configure(text="Browser failed to open", text_color=ERROR)
            self._login_status.configure(
                text="Could not launch Chromium. Check the Send tab log for details.",
                text_color=ERROR,
            )
            self._update_status("Browser launch failed", ERROR)
            return

        if already_logged_in:
            self._on_session_confirmed()
        else:
            # Browser is open, user needs to log in manually
            self._check_session_btn.configure(state="normal")
            self._login_state_badge.configure(text="Waiting for Login...", text_color=WARNING)
            self._login_status.configure(
                text="Browser is open — log in to Instagram, then click the green button below.",
                text_color=WARNING,
            )
            self._update_status("Waiting for login...", WARNING)
            self._start_session_poll()


    def _start_session_poll(self):
        """Poll check_session() every 2.5 seconds until login is confirmed."""
        async def _poll():
            logged_in = await self._engine.check_session()
            self.after(0, lambda: self._on_poll_result(logged_in))
        self._run_async(_poll())

    def _on_poll_result(self, logged_in: bool):
        if logged_in:
            self._on_session_confirmed()
        else:
            self._session_poll_id = self.after(2500, self._start_session_poll)

    def _manual_check_session(self):
        """User clicked 'I'm Logged In' button."""
        self._login_status.configure(text="Checking session...", text_color=WARNING)

        async def _check():
            logged_in = await self._engine.check_session()
            self.after(0, lambda: self._on_poll_result(logged_in))
            if not logged_in:
                self.after(0, lambda: self._login_status.configure(
                    text="Not logged in yet. Please complete login in the browser.",
                    text_color=ERROR,
                ))

        self._run_async(_check())

    def _on_session_confirmed(self):
        """Called when login is confirmed — update all UI elements."""
        if self._session_poll_id:
            self.after_cancel(self._session_poll_id)
            self._session_poll_id = None
        self._check_session_btn.configure(state="disabled")
        self._login_state_badge.configure(text="Connected  \u2714", text_color=SUCCESS)
        self._login_status.configure(
            text="Session active. You can now run campaigns!",
            text_color=SUCCESS,
        )
        self._open_browser_btn.configure(
            text="\U0001f310  Browser Connected  \u2714",
            fg_color="#1A3A1A",
            text_color=SUCCESS,
        )
        self._update_status("Logged in to Instagram", SUCCESS)


    # ══════════════════════════════════════════════════════════════════════════
    # CONTACTS TAB
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_contacts(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._main, fg_color=BG_DARK)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # ── Header bar ──────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=0, height=64)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            hdr, text="👥  Contacts",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT_PRI
        ).grid(row=0, column=0, padx=24, pady=16, sticky="w")

        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=16, pady=8, sticky="e")

        ctk.CTkButton(
            btn_frame, text="📂  Import Contacts (CSV/Excel/TXT)",
            fg_color=ACCENT, hover_color=ACCENT_HOV, height=36,
            font=ctk.CTkFont(size=13), command=self._import_contacts,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_frame, text="🗑  Clear All",
            fg_color="#3B1E1E", hover_color="#5C2A2A", height=36,
            text_color=ERROR, font=ctk.CTkFont(size=13),
            command=self._clear_contacts,
        ).pack(side="left", padx=4)

        self._contacts_count_lbl = ctk.CTkLabel(
            btn_frame, text="0 contacts",
            font=ctk.CTkFont(size=12), text_color=TEXT_SEC
        )
        self._contacts_count_lbl.pack(side="left", padx=12)

        # ── Table ───────────────────────────────────────────────────────────
        table_frame = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=12)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)

        # Header row
        cols   = ["Username", "Name", "Status", "Error", "Sent At"]
        widths = [200, 180, 100, 300, 160]
        col_hdr = ctk.CTkFrame(table_frame, fg_color="#13132A", height=36)
        col_hdr.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        for c_idx, (col, w) in enumerate(zip(cols, widths)):
            ctk.CTkLabel(
                col_hdr, text=col, width=w, anchor="w",
                font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_SEC
            ).grid(row=0, column=c_idx, padx=(16 if c_idx == 0 else 4, 0), pady=8, sticky="w")

        # Scrollable body
        self._contacts_scroll = ctk.CTkScrollableFrame(
            table_frame, fg_color="transparent", corner_radius=0
        )
        self._contacts_scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self._contacts_scroll.grid_columnconfigure(0, weight=1)

        return frame

    def _refresh_contacts_table(self):
        # Clear old rows
        for widget in self._contacts_scroll.winfo_children():
            widget.destroy()

        contacts = db.get_all_contacts()
        self._contacts_count_lbl.configure(text=f"{len(contacts)} contacts")

        status_colors = {"Pending": TEXT_SEC, "Sent": SUCCESS, "Failed": ERROR}
        for i, c in enumerate(contacts):
            row_bg = BG_CARD if i % 2 == 0 else "#1C1C35"
            row    = ctk.CTkFrame(self._contacts_scroll, fg_color=row_bg, height=36, corner_radius=0)
            row.grid(row=i, column=0, sticky="ew", pady=0)

            data   = [c["username"], c["name"] or "—", c["status"], c["error_msg"] or "", c["sent_at"] or ""]
            widths = [200, 180, 100, 300, 160]
            sc     = status_colors.get(c["status"], TEXT_SEC)
            for c_idx, (val, w) in enumerate(zip(data, widths)):
                color = sc if c_idx == 2 else TEXT_PRI
                ctk.CTkLabel(
                    row, text=str(val)[:60], width=w, anchor="w",
                    font=ctk.CTkFont(size=12), text_color=color
                ).grid(row=0, column=c_idx, padx=(16 if c_idx == 0 else 4, 0), pady=6, sticky="w")

    def _import_contacts(self):
        path = filedialog.askopenfilename(
            title="Import Contacts",
            filetypes=[
                ("All Supported Files", "*.csv *.xlsx *.xls *.txt"),
                ("Text Files (*.txt)", "*.txt"),
                ("CSV Files (*.csv)", "*.csv"),
                ("Excel Files (*.xlsx, *.xls)", "*.xlsx *.xls"),
                ("All files", "*.*")
            ],
        )
        if not path:
            return
        imported, skipped, errors = imp.import_contacts(path)
        msg = f"Imported: {imported}\nSkipped / Duplicates: {skipped}"
        if errors:
            msg += f"\nErrors:\n" + "\n".join(errors[:5])
        messagebox.showinfo("Import Complete", msg)
        self._refresh_contacts_table()
        self._update_status(f"Imported {imported} contacts", SUCCESS)

    def _clear_contacts(self):
        if messagebox.askyesno("Clear Contacts", "Delete ALL contacts from the list?"):
            db.clear_contacts()
            self._refresh_contacts_table()
            self._update_status("Contacts cleared", WARNING)

    # ══════════════════════════════════════════════════════════════════════════
    # TEMPLATE TAB
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_template(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._main, fg_color=BG_DARK)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=0, height=64)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(
            hdr, text="✉️  Message Template",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT_PRI
        ).place(x=24, rely=0.5, anchor="w")

        # Card
        card = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=12)
        card.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        # Variable hints
        hints = ctk.CTkFrame(card, fg_color="#1A1A35", corner_radius=8)
        hints.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        ctk.CTkLabel(
            hints,
            text="💡  Available variables:   {{name}}  ·  {{username}}",
            font=ctk.CTkFont(size=12), text_color=TEXT_SEC
        ).pack(padx=16, pady=10)

        # Text area
        self._template_box = ctk.CTkTextbox(
            card, fg_color="#1E1E3A", text_color=TEXT_PRI, border_color=BORDER,
            font=ctk.CTkFont(family="Consolas", size=14),
            wrap="word", corner_radius=10,
        )
        self._template_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        self._template_box.bind("<KeyRelease>", self._update_char_count)

        # Footer
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        foot.grid_columnconfigure(0, weight=1)

        self._char_count_lbl = ctk.CTkLabel(
            foot, text="0 characters",
            font=ctk.CTkFont(size=11), text_color=TEXT_SEC
        )
        self._char_count_lbl.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            foot, text="💾  Save Template",
            fg_color=ACCENT, hover_color=ACCENT_HOV, height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._save_template,
        ).grid(row=0, column=1, sticky="e")

        return frame

    def _update_char_count(self, _=None):
        text = self._template_box.get("1.0", "end-1c")
        self._char_count_lbl.configure(text=f"{len(text)} characters")

    def _load_template_from_db(self):
        tmpl = db.get_setting("message_template", "")
        self._template_box.delete("1.0", "end")
        self._template_box.insert("1.0", tmpl)
        self._update_char_count()

    def _save_template(self):
        tmpl = self._template_box.get("1.0", "end-1c").strip()
        if not tmpl:
            messagebox.showwarning("Empty Template", "Please enter a message template.")
            return
        db.save_setting("message_template", tmpl)
        self._update_status("Template saved ✅", SUCCESS)
        messagebox.showinfo("Saved", "Message template saved successfully!")

    # ══════════════════════════════════════════════════════════════════════════
    # SEND TAB
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_send(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._main, fg_color=BG_DARK)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        # Header
        hdr = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=0, height=64)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(
            hdr, text="🚀  Send Campaign",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT_PRI
        ).place(x=24, rely=0.5, anchor="w")

        # Controls card
        ctrl = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=12)
        ctrl.grid(row=1, column=0, sticky="ew", padx=20, pady=(20, 8))
        ctrl.grid_columnconfigure(2, weight=1)

        self._start_btn = ctk.CTkButton(
            ctrl, text="▶  Start Campaign",
            fg_color=SUCCESS, hover_color="#16A34A", height=50, width=180,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._start_campaign,
        )
        self._start_btn.grid(row=0, column=0, padx=16, pady=16)

        self._stop_btn = ctk.CTkButton(
            ctrl, text="⬛  Stop",
            fg_color="#7F1D1D", hover_color=ERROR, height=50, width=120,
            font=ctk.CTkFont(size=14, weight="bold"), command=self._stop_campaign,
            state="disabled",
        )
        self._stop_btn.grid(row=0, column=1, padx=8, pady=16)

        prog_frame = ctk.CTkFrame(ctrl, fg_color="transparent")
        prog_frame.grid(row=0, column=2, padx=16, pady=16, sticky="ew")
        prog_frame.grid_columnconfigure(0, weight=1)

        self._progress_bar = ctk.CTkProgressBar(
            prog_frame, height=12, progress_color=ACCENT, fg_color="#2D2D4E",
        )
        self._progress_bar.set(0)
        self._progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self._progress_lbl = ctk.CTkLabel(
            prog_frame, text="0 / 0 sent",
            font=ctk.CTkFont(size=12), text_color=TEXT_SEC
        )
        self._progress_lbl.grid(row=1, column=0, sticky="w")

        self._send_status_lbl = ctk.CTkLabel(
            ctrl, text="Idle", font=ctk.CTkFont(size=12), text_color=TEXT_SEC
        )
        self._send_status_lbl.grid(row=0, column=3, padx=16, pady=16)

        # Log viewer
        log_card = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=12)
        log_card.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 0))
        log_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            log_hdr, text="📋  Activity Log",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_PRI
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            log_hdr, text="Clear Log", width=80, height=28, fg_color="transparent",
            border_color=BORDER, border_width=1, text_color=TEXT_SEC, font=ctk.CTkFont(size=11),
            command=self._clear_log_box,
        ).grid(row=0, column=1)

        self._log_box = ctk.CTkTextbox(
            log_card, fg_color="#0D0D1F", text_color=TEXT_PRI,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=8, state="disabled",
        )
        self._log_box.grid(row=1, column=0, sticky="nsew", padx=16, pady=(8, 16))

        return frame

    def _start_campaign(self):
        contacts = db.get_pending_contacts()
        if not contacts:
            messagebox.showinfo("No Contacts", "No pending contacts. Import contacts first.")
            return
        template = db.get_setting("message_template", "")
        if not template:
            messagebox.showwarning("No Template", "Please create a message template first.")
            return
        if db.get_setting("session_active", "0") != "1":
            messagebox.showwarning(
                "Not Logged In",
                "Please log in to Instagram first.\n\nGo to the Login tab and click 'Open Instagram in Browser'.",
            )
            return

        self._stop_event.clear()
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._send_status_lbl.configure(text="Running...", text_color=SUCCESS)
        self._progress_bar.set(0)
        self._progress_lbl.configure(text=f"0 / {len(contacts)} sent")
        self._update_status("Campaign running...", SUCCESS)

        settings = db.get_all_settings()

        async def _campaign_coro():
            await self._engine.send_campaign(
                contacts=contacts,
                message_template=template,
                settings=settings,
                stop_event=self._stop_event,
                progress_callback=self._on_progress,
                browser_path=settings.get("browser_path", ""),
            )
            self.after(0, self._on_campaign_done)

        self._campaign_future = self._run_async(_campaign_coro())

    def _stop_campaign(self):
        self._stop_event.set()          # threading.Event — safe from any thread
        if self._engine:
            self._engine.stop()
        self._stop_btn.configure(state="disabled")
        self._send_status_lbl.configure(text="Stopping...", text_color=WARNING)
        self._update_status("Stopping campaign...", WARNING)

    def _on_campaign_done(self):
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._send_status_lbl.configure(text="Done", text_color=SUCCESS)
        self._update_status("Campaign complete", SUCCESS)
        self._refresh_contacts_table()

    def _on_progress(self, sent: int, total: int):
        pct = sent / total if total else 0
        self.after(0, lambda: self._progress_bar.set(pct))
        self.after(0, lambda: self._progress_lbl.configure(text=f"{sent} / {total} sent"))

    def _safe_log(self, msg: str):
        """Thread-safe log append."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.after(0, lambda: self._append_log(f"[{ts}] {msg}"))

    def _append_log(self, msg: str):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")
        self._send_status_lbl.configure(text=msg[:60])

    def _clear_log_box(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # SETTINGS TAB
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_settings(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._main, fg_color=BG_DARK)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=0, height=64)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        ctk.CTkLabel(
            hdr, text="⚙️  Settings",
            font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT_PRI
        ).place(x=24, rely=0.5, anchor="w")

        # Scrollable settings area
        scroll = ctk.CTkScrollableFrame(frame, fg_color=BG_DARK)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        def section(parent, title: str, row: int):
            f = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
            f.grid(row=row, column=0, sticky="ew", padx=20, pady=(12, 0))
            f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                f, text=title,
                font=ctk.CTkFont(size=14, weight="bold"), text_color=ACCENT
            ).grid(row=0, column=0, columnspan=2, padx=20, pady=(16, 8), sticky="w")
            return f

        def field(parent, label: str, row: int, default: str = "") -> ctk.CTkEntry:
            ctk.CTkLabel(parent, text=label, text_color=TEXT_SEC, font=ctk.CTkFont(size=13)).grid(
                row=row, column=0, padx=20, pady=6, sticky="w"
            )
            e = ctk.CTkEntry(
                parent, height=38, fg_color="#1E1E3A", border_color=BORDER,
                text_color=TEXT_PRI, font=ctk.CTkFont(size=13),
            )
            e.insert(0, default)
            e.grid(row=row, column=1, padx=20, pady=6, sticky="ew")
            return e

        # Timing section
        timing = section(scroll, "⏱  Timing & Limits", 0)
        self._s_min_delay        = field(timing, "Min Delay (seconds)",         1, "60")
        self._s_max_delay        = field(timing, "Max Delay (seconds)",         2, "180")
        self._s_daily_limit      = field(timing, "Daily Message Limit",         3, "30")
        self._s_batch_size       = field(timing, "Batch Size",                  4, "10")
        self._s_batch_break_min  = field(timing, "Batch Break Min (minutes)",   5, "20")
        self._s_batch_break_max  = field(timing, "Batch Break Max (minutes)",   6, "30")
        ctk.CTkFrame(timing, height=12, fg_color="transparent").grid(row=7, column=0)

        # Browser section
        browser = section(scroll, "🌐  Browser", 1)
        ctk.CTkLabel(browser, text="Browser Executable Path (optional)",
                     text_color=TEXT_SEC, font=ctk.CTkFont(size=13)).grid(
            row=1, column=0, padx=20, pady=6, sticky="w"
        )
        bp_frame = ctk.CTkFrame(browser, fg_color="transparent")
        bp_frame.grid(row=1, column=1, padx=20, pady=6, sticky="ew")
        bp_frame.grid_columnconfigure(0, weight=1)
        self._s_browser_path = ctk.CTkEntry(
            bp_frame, height=38, fg_color="#1E1E3A", border_color=BORDER,
            text_color=TEXT_PRI, font=ctk.CTkFont(size=13),
            placeholder_text="Leave empty to use bundled Chromium",
        )
        self._s_browser_path.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            bp_frame, text="Browse", width=80, height=38,
            fg_color=ACCENT, hover_color=ACCENT_HOV, font=ctk.CTkFont(size=12),
            command=self._browse_browser,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkFrame(browser, height=12, fg_color="transparent").grid(row=2, column=0)

        # Save button
        ctk.CTkButton(
            scroll, text="💾  Save Settings",
            fg_color=ACCENT, hover_color=ACCENT_HOV, height=48,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._save_settings,
        ).grid(row=2, column=0, sticky="ew", padx=20, pady=24)

        return frame

    def _browse_browser(self):
        path = filedialog.askopenfilename(
            title="Select Browser Executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self._s_browser_path.delete(0, "end")
            self._s_browser_path.insert(0, path)

    def _load_settings_from_db(self):
        s = db.get_all_settings()
        fields = {
            "min_delay":       self._s_min_delay,
            "max_delay":       self._s_max_delay,
            "daily_limit":     self._s_daily_limit,
            "batch_size":      self._s_batch_size,
            "batch_break_min": self._s_batch_break_min,
            "batch_break_max": self._s_batch_break_max,
            "browser_path":    self._s_browser_path,
        }
        for key, widget in fields.items():
            val = s.get(key, "")
            widget.delete(0, "end")
            widget.insert(0, val)

    def _save_settings(self):
        mapping = {
            "min_delay":       self._s_min_delay.get(),
            "max_delay":       self._s_max_delay.get(),
            "daily_limit":     self._s_daily_limit.get(),
            "batch_size":      self._s_batch_size.get(),
            "batch_break_min": self._s_batch_break_min.get(),
            "batch_break_max": self._s_batch_break_max.get(),
            "browser_path":    self._s_browser_path.get(),
        }
        for key, val in mapping.items():
            db.save_setting(key, val)
        self._update_status("Settings saved ✅", SUCCESS)
        messagebox.showinfo("Saved", "Settings saved successfully!")
