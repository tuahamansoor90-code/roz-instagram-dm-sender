# 🟣 Instagram DM Sender

**A licensed Python desktop automation tool for sending personalized bulk direct messages on Instagram.**

Built with Playwright async browser automation, CustomTkinter GUI, and a hardware-locked licensing system — packaged as a standalone Windows `.exe`.

---

## ✨ Features

- **Persistent Session** — Login once (password, Google OAuth, or any method); session cookies are saved and reused automatically
- **Anti-Ban Engine** — Human-like typing, randomized delays, batch size limits, and cooling breaks between batches
- **Stealth Mode** — JavaScript patches override `navigator.webdriver`, inject fake plugin lists, and spoof browser locale/timezone
- **Instagram-Specific Handling** — Dismisses pop-up dialogs, story overlays, and handles dynamic route changes automatically
- **Smart Contact Importer** — Supports CSV and TXT files; auto-normalizes usernames
- **Message Templates** — Use `{{name}}` placeholder for personalized messages
- **Real-Time Dashboard** — Live scrollable log with sent/failed/remaining tracking per contact
- **Hardware-Locked License** — HMAC-SHA256 signed keys tied to MAC address; expiry verified via online HTTP clock (tamper-proof)
- **Standalone Executable** — Packaged with PyInstaller; auto-installs Playwright Chromium on first run

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Automation | Playwright (async) |
| GUI | CustomTkinter |
| Database | SQLite |
| Concurrency | asyncio + threading |
| Data Import | Pandas, openpyxl |
| Security | HMAC-SHA256 |
| Packaging | PyInstaller |

---

## 📁 Project Structure

```
Instagram/
├── main.py                 # Entry point — license check, Chromium install, GUI launch
├── instagram_engine.py     # Async Playwright engine (anti-ban, stealth, session, DM flow)
├── ui.py                   # CustomTkinter GUI (Login, Contacts, Campaign, Settings tabs)
├── database.py             # SQLite interface — contacts, settings, logs
├── importer.py             # CSV/TXT contact importer with username normalization
├── license_verifier.py     # HMAC-SHA256 hardware-locked license system
├── generate_key.py         # License key generator (admin tool)
├── requirements.txt        # Python dependencies
└── build_assets/
    └── generate_icon.py    # App icon generator
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.11+ installed on Windows
- Add Python to PATH during installation

### 1. Clone the Repository
```bash
git clone https://github.com/tuahamansoor90-code/roz-instagram-dm-sender.git
cd roz-instagram-dm-sender
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Run the Application
```bash
python main.py
```

> **Note:** A valid license key is required to launch the application.

---

## 📖 How to Use

1. **Login** — Click **Open Browser & Login**, log into Instagram using any method (password, Google, saved session), then click **Check Session**
2. **Import Contacts** — Go to the **Contacts** tab and import a CSV or TXT file with Instagram usernames
3. **Compose Message** — Write your message template using `{{name}}` for personalization
4. **Configure Settings** — Set min/max delay, daily limit, batch size, and batch break duration
5. **Start Campaign** — Click **Start Campaign** and monitor progress in the live log

---

## ⚙️ Settings Reference

| Setting | Description |
|---------|-------------|
| Min Delay | Minimum wait time between messages |
| Max Delay | Maximum wait time between messages |
| Daily Limit | Maximum messages to send per session |
| Batch Size | Number of messages before taking a cooling break |
| Batch Break | Duration of the cooling break between batches |

---

## 📦 Build as Executable

```bash
pip install pyinstaller
pyinstaller RozInstagramDMSender.spec
```

The compiled `.exe` will appear in `dist/`.

---

## ⚠️ Disclaimer

This tool is intended for legitimate marketing and outreach purposes only. Users are solely responsible for complying with Instagram's Terms of Service and applicable laws. The developer assumes no liability for misuse.

---

## 👨‍💻 Developer

**Roz Services Network**
GitHub: [@tuahamansoor90-code](https://github.com/tuahamansoor90-code)
