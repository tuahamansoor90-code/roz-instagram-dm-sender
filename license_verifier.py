import os
import sys
import uuid
import hmac
import hashlib
import base64
import urllib.request
import email.utils
from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

import database as db

# Unique product secret key for Instagram DM Sender
SECRET_KEY = b"roz_instagram_dm_sender_secure_secret_key_2026"

# Color Palette matching the main app
BG_DARK    = "#0F0F1A"
BG_CARD    = "#1A1A2E"
ACCENT     = "#7C3AED"        # purple
ACCENT_HOV = "#6D28D9"
TEXT_PRI   = "#F1F5F9"
TEXT_SEC   = "#94A3B8"
SUCCESS    = "#22C55E"
ERROR      = "#EF4444"
WARNING    = "#F59E0B"
BORDER     = "#2D2D4E"


def get_hwid():
    """Generates a unique 16-character Hardware ID based on the machine's MAC address."""
    node = uuid.getnode()
    raw = f"ROZ-INSTAGRAM-{node}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def get_online_date():
    """Retrieves the current date from online servers using HTTP headers to prevent clock tampering."""
    urls = [
        "https://www.google.com",
        "https://www.wikipedia.org",
        "https://www.microsoft.com"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=5) as response:
                date_str = response.headers.get('Date')
                if date_str:
                    dt = email.utils.parsedate_to_datetime(date_str)
                    return dt.date()
        except Exception:
            continue
    return None


def parse_and_verify_key(key_str, current_hwid):
    """
    Decodes the 36-character key and validates its signature and HWID.
    Returns: (info_dict, error_message)
    """
    clean_key = key_str.upper().replace("-", "").replace(" ", "")
    if len(clean_key) != 36:
        return None, "Invalid license key format (must be 36 characters)."
        
    # Re-apply Base32 padding if missing
    padding = (8 - len(clean_key) % 8) % 8
    padded_str = clean_key + ("=" * padding)
    
    try:
        key_bytes = base64.b32decode(padded_str)
    except Exception:
        return None, "Invalid key characters."
        
    if len(key_bytes) != 22:
        return None, "Invalid key structure."
        
    payload = key_bytes[:14]
    sig = key_bytes[14:]
    
    # Verify signature
    expected_sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).digest()[:8]
    if not hmac.compare_digest(sig, expected_sig):
        return None, "Invalid license key signature (tampered key)."
        
    # Unpack dates (3 bytes start, 3 bytes end)
    start_yr = payload[0] + 2000
    start_mo = payload[1]
    start_dy = payload[2]
    
    end_yr = payload[3] + 2000
    end_mo = payload[4]
    end_dy = payload[5]
    
    hwid_bytes = payload[6:14]
    
    try:
        start_date = date(start_yr, start_mo, start_dy)
        end_date = date(end_yr, end_mo, end_dy)
    except ValueError:
        return None, "License key contains invalid dates."
        
    # Verify HWID
    is_any_hwid = (hwid_bytes == b'\xff' * 8)
    key_hwid = "ANY" if is_any_hwid else hwid_bytes.hex().upper()
    
    if not is_any_hwid and key_hwid != current_hwid:
        return None, f"Key bound to another PC (HWID: {key_hwid})."
        
    return {
        "start_date": start_date,
        "end_date": end_date,
        "hwid": key_hwid
    }, None


def is_license_active():
    """
    Fast verification check used while the app is running.
    Returns: (is_valid, status_msg)
    """
    key = db.get_setting("license_key")
    if not key:
        return False, "Product is not activated."
        
    current_hwid = get_hwid()
    online_date = get_online_date()
    if not online_date:
        return False, "Requires internet connection to verify date."
        
    info, error = parse_and_verify_key(key, current_hwid)
    if error:
        return False, error
        
    if online_date < info["start_date"]:
        return False, f"Key not active yet (starts: {info['start_date']})."
    if online_date > info["end_date"]:
        return False, f"Key expired on {info['end_date']}."
        
    return True, f"Active (Expires: {info['end_date']})"


class LicenseActivationWindow(ctk.CTk):
    """Modern dark purple/blue activation GUI dialog if no active license key is found."""
    def __init__(self):
        super().__init__()
        
        self.activated = False
        
        # Configure Window
        self.title("Product Activation")
        self.geometry("520x360")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        
        # Centering the window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header Frame
        header = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color=BG_CARD, border_width=1, border_color=BORDER)
        header.pack(fill="x")
        
        header_lbl = ctk.CTkLabel(
            header,
            text="Instagram DM Sender Activation",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRI
        )
        header_lbl.pack(pady=20)
        
        # Main Body Frame
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=25, pady=15)
        
        # Hardware ID section
        hwid_frame = ctk.CTkFrame(body, fg_color="transparent")
        hwid_frame.pack(fill="x", pady=(5, 10))
        
        hwid_lbl = ctk.CTkLabel(
            hwid_frame,
            text="Your Hardware ID (HWID):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_SEC
        )
        hwid_lbl.pack(side="left")
        
        self.hwid_val = get_hwid()
        self.hwid_entry = ctk.CTkEntry(
            hwid_frame,
            width=180,
            font=ctk.CTkFont(size=11, family="Consolas"),
            fg_color=BG_DARK,
            border_color=BORDER,
            text_color=TEXT_PRI
        )
        self.hwid_entry.insert(0, self.hwid_val)
        self.hwid_entry.configure(state="readonly")
        self.hwid_entry.pack(side="left", padx=10)
        
        copy_btn = ctk.CTkButton(
            hwid_frame,
            text="Copy HWID",
            width=80,
            height=26,
            fg_color=BG_CARD,
            hover_color=BORDER,
            text_color=TEXT_PRI,
            command=self.copy_hwid
        )
        copy_btn.pack(side="left")
        
        # License key prompt
        key_lbl = ctk.CTkLabel(
            body,
            text="Enter License Key:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_SEC
        )
        key_lbl.pack(anchor="w", pady=(10, 2))
        
        self.key_entry = ctk.CTkEntry(
            body,
            placeholder_text="XXXXXX-XXXXXX-XXXXXX-XXXXXX-XXXXXX-XXXXXX",
            font=ctk.CTkFont(size=12, family="Consolas"),
            fg_color=BG_DARK,
            border_color=BORDER,
            text_color=TEXT_PRI
        )
        self.key_entry.pack(fill="x", pady=5)
        
        # Status message
        self.status_lbl = ctk.CTkLabel(
            body,
            text="Please enter a valid serial key to activate the software.",
            text_color=TEXT_SEC,
            font=ctk.CTkFont(size=11, slant="italic"),
            wraplength=460,
            justify="left"
        )
        self.status_lbl.pack(anchor="w", pady=5)
        
        # Action Buttons
        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(15, 0))
        
        self.activate_btn = ctk.CTkButton(
            btn_frame,
            text="Verify & Activate",
            fg_color=ACCENT,
            hover_color=ACCENT_HOV,
            text_color=TEXT_PRI,
            font=ctk.CTkFont(weight="bold"),
            command=self.handle_activation
        )
        self.activate_btn.pack(side="right", padx=(5, 0))
        
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Exit App",
            fg_color="#3B1E1E",
            hover_color="#5C2A2A",
            text_color=ERROR,
            command=self.destroy
        )
        cancel_btn.pack(side="right", padx=(0, 5))

    def copy_hwid(self):
        self.clipboard_clear()
        self.clipboard_append(self.hwid_val)
        messagebox.showinfo("Copied", "Hardware ID copied to clipboard.")
        
    def handle_activation(self):
        entered_key = self.key_entry.get().strip()
        if not entered_key:
            self.status_lbl.configure(text="Key field cannot be empty.", text_color=ERROR)
            return
            
        self.status_lbl.configure(text="Checking internet and validating key...", text_color=WARNING)
        self.update()
        
        # Check internet
        online_date = get_online_date()
        if not online_date:
            self.status_lbl.configure(
                text="Verification Failed: No internet connection.\nActive internet is required to verify the date.",
                text_color=ERROR
            )
            return
            
        info, error = parse_and_verify_key(entered_key, self.hwid_val)
        if error:
            self.status_lbl.configure(text=f"Verification Failed: {error}", text_color=ERROR)
            return
            
        # Check expiry dates
        if online_date < info["start_date"]:
            self.status_lbl.configure(
                text=f"License not active yet. Starts on: {info['start_date']}",
                text_color=ERROR
            )
            return
        if online_date > info["end_date"]:
            self.status_lbl.configure(
                text=f"License expired. Expired on: {info['end_date']}",
                text_color=ERROR
            )
            return
            
        # Success!
        db.save_setting("license_key", entered_key)
        self.activated = True
        messagebox.showinfo(
            "Activation Successful",
            f"Thank you for activating!\nYour product license is valid until: {info['end_date']}"
        )
        self.destroy()


def verify_or_activate_license():
    """
    Verifies if a valid license exists. If not, opens the activation window.
    Returns: True if activated/valid, False if canceled or invalid.
    """
    # Fast check first
    is_valid, _ = is_license_active()
    if is_valid:
        return True
        
    # Open Activation Dialog
    app = LicenseActivationWindow()
    app.mainloop()
    return app.activated
