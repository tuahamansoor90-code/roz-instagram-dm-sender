"""
instagram_engine.py - Playwright Automation Engine for Instagram DM Sender
Anti-ban rules are baked in: human-like typing, random delays, batch breaks.

LOGIN FLOW (simplified):
  1. open_browser()  → opens Chromium, navigates to Instagram login page
  2. User logs in manually in the browser (any method: password, Google, etc.)
  3. check_session() → polls until logged in, returns True when session is ready
  4. Session is stored in instagram_session/ and reused on every subsequent launch
"""

import asyncio
import os
import random
import re
import threading
from datetime import datetime
from typing import Callable

from playwright.async_api import async_playwright, BrowserContext, Page

import database as db

# ── Paths ──────────────────────────────────────────────────────────────────────
import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SESSION_DIR     = os.path.join(BASE_DIR, "instagram_session")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

os.makedirs(SESSION_DIR,     exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# ── Anti-detection browser args ────────────────────────────────────────────────
LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--lang=en-US",
    "--disable-extensions",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--start-maximized",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

INSTAGRAM_URL    = "https://www.instagram.com"
INSTAGRAM_LOGIN  = "https://www.instagram.com/accounts/login/"
INSTAGRAM_DM_NEW = "https://www.instagram.com/direct/new/"


# ══════════════════════════════════════════════════════════════════════════════
class InstagramEngine:
    """
    Manages a persistent Playwright Chromium context for Instagram DM sending.
    All public methods are async; submit them via run_coroutine_threadsafe().
    """

    def __init__(self, log_callback: Callable[[str], None] | None = None):
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page:    Page | None = None
        self._running  = False
        self._log = log_callback or print

    # ── Browser lifecycle ──────────────────────────────────────────────────────

    async def _start_browser(self, browser_path: str = "") -> None:
        """Launch (or reuse) the persistent Chromium context."""
        if self._context is not None:
            return  # already running

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        kwargs = dict(
            user_data_dir = SESSION_DIR,
            user_agent    = USER_AGENT,
            args          = LAUNCH_ARGS,
            headless      = False,
            locale        = "en-US",
            timezone_id   = "America/New_York",
        )
        if browser_path and os.path.exists(browser_path):
            kwargs["executable_path"] = browser_path

        self._context = await self._playwright.chromium.launch_persistent_context(**kwargs)
        self._page = (
            self._context.pages[0]
            if self._context.pages
            else await self._context.new_page()
        )

        # Stealth JS patches
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver',  { get: () => undefined });
            Object.defineProperty(navigator, 'languages',  { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins',    { get: () => [1, 2, 3, 4, 5] });
        """)

    async def close(self) -> None:
        """Close browser and Playwright runtime."""
        self._running = False
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        finally:
            self._context = None

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None

    # ── Session helpers ────────────────────────────────────────────────────────

    def has_saved_session(self) -> bool:
        """
        Returns True if a previous session folder exists and has data,
        meaning the user has logged in before (cookies are saved).
        """
        try:
            marker_files = [
                os.path.join(SESSION_DIR, "Default", "Cookies"),
                os.path.join(SESSION_DIR, "Default", "Local Storage"),
            ]
            return any(os.path.exists(p) for p in marker_files)
        except Exception:
            return False

    async def _is_logged_in(self) -> bool:
        """
        Check if the current page shows an authenticated Instagram session.
        Works on any Instagram page.
        """
        try:
            if self._page is None:
                return False
            url = self._page.url
            if not url.startswith("https://www.instagram.com"):
                return False
            if "accounts/login" in url:
                return False
            if "challenge" in url:
                return False

            # Confirmed-login indicators: the main nav svg icons only appear when logged in
            # Try multiple selectors for robustness
            selectors = [
                'svg[aria-label="Home"]',
                'a[href="/"][role="link"]',
                'a[href="/direct/inbox/"]',
                'span[aria-label="Home"]',
                'div[role="navigation"] a[href="/"]',
            ]
            for sel in selectors:
                try:
                    count = await self._page.locator(sel).count()
                    if count > 0:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    # ── One-click open browser ─────────────────────────────────────────────────

    async def open_browser(self, browser_path: str = "") -> tuple[bool, bool]:
        """
        Open the browser and navigate to Instagram.

        Returns:
            (opened_ok, already_logged_in)
            - (False, False) → browser failed to launch
            - (True, False)  → browser open, user needs to log in
            - (True, True)   → browser open, session already active
        """
        try:
            self._log("Launching Chromium browser...")
            await self._start_browser(browser_path)
            self._log("Browser launched. Loading Instagram...")
            page = self._page

            await page.goto(INSTAGRAM_URL, wait_until="domcontentloaded", timeout=30_000)
            await self._random_wait(1, 2)

            if await self._is_logged_in():
                self._log("Session restored — already logged in!")
                db.save_setting("session_active", "1")
                return True, True

            # Go to login page
            self._log("Please log in to Instagram in the browser.")
            await page.goto(INSTAGRAM_LOGIN, wait_until="domcontentloaded", timeout=30_000)

            # Accept cookies banner if shown
            try:
                for text in ["Allow all cookies", "Accept All", "Allow essential and optional cookies"]:
                    btn = page.locator(f"text={text}").first
                    if await btn.is_visible(timeout=2_000):
                        await btn.click()
                        await self._random_wait(0.5, 1)
                        break
            except Exception:
                pass

            return True, False

        except Exception as e:
            self._log(f"ERROR launching browser: {e}")
            return False, False


    async def check_session(self) -> bool:
        """
        Poll the current page to see if the user has logged in.
        Called repeatedly by the UI every 2 seconds after open_browser().
        Returns True once the session is confirmed.
        """
        try:
            if self._page is None:
                return False
            # Navigate to home if still on login page, so we can confirm login
            current = self._page.url
            if "accounts/login" in current or current.rstrip("/") == INSTAGRAM_URL:
                # Just check current page without navigating
                pass
            elif "challenge" in current or "two_factor" in current:
                # User is doing 2FA — wait
                return False

            logged = await self._is_logged_in()
            if logged:
                self._log("Session confirmed — logged in successfully!")
                db.save_setting("session_active", "1")
                db.save_setting("logged_in_user", await self._get_username())
            return logged
        except Exception:
            return False

    async def _get_username(self) -> str:
        """Try to extract the logged-in username from the page."""
        try:
            # Look for profile link in nav (format: /username/)
            links = self._page.locator('a[href*="/"][role="link"]')
            count = await links.count()
            for i in range(count):
                href = await links.nth(i).get_attribute("href") or ""
                # Profile links are like /username/ — single segment
                parts = [p for p in href.split("/") if p]
                if len(parts) == 1 and not parts[0].startswith("_"):
                    return parts[0]
        except Exception:
            pass
        return ""

    # ── Send DMs ───────────────────────────────────────────────────────────────

    async def send_campaign(
        self,
        contacts: list[dict],
        message_template: str,
        settings: dict,
        stop_event: threading.Event,
        progress_callback: Callable[[int, int], None] | None = None,
        browser_path: str = "",
    ) -> None:
        """
        Main campaign loop. Sends DMs to all pending contacts.
        Respects batch breaks, daily limits, and stop_event.
        """
        self._running = True

        min_delay       = int(settings.get("min_delay",       60))
        max_delay       = int(settings.get("max_delay",      180))
        daily_limit     = int(settings.get("daily_limit",     30))
        batch_size      = int(settings.get("batch_size",      10))
        batch_break_min = int(settings.get("batch_break_min", 20))
        batch_break_max = int(settings.get("batch_break_max", 30))

        sent_today = db.get_sent_count_today()
        sent_batch = 0
        total      = len(contacts)
        sent_total = 0

        # Ensure browser is open
        if not self._context:
            await self._start_browser(browser_path)

        if not await self._is_logged_in():
            self._log("Not logged in! Please log in first via the Login tab.")
            return

        for i, contact in enumerate(contacts):
            if stop_event.is_set():
                self._log("Campaign stopped by user.")
                break

            if sent_today >= daily_limit:
                self._log(f"Daily limit of {daily_limit} messages reached. Stopping.")
                break

            username = contact["username"]
            name     = contact.get("name") or username

            self._log(f"[{i+1}/{total}] Sending to @{username}...")

            # Batch cooling break
            if sent_batch > 0 and sent_batch % batch_size == 0:
                mins = random.randint(batch_break_min, batch_break_max)
                secs = mins * 60
                self._log(f"Batch of {batch_size} done. Cooling down for {mins} min...")
                await self._interruptible_sleep(secs, stop_event)
                if stop_event.is_set():
                    break

            # Personalize message
            message = (
                message_template
                .replace("{{name}}", name)
                .replace("{{username}}", username)
            )

            success, error = await self._send_dm(username, message, stop_event)

            if success:
                db.update_contact_status(username, "Sent")
                db.add_log(username, name, "Sent")
                sent_today  += 1
                sent_batch  += 1
                sent_total  += 1
                self._log(f"Sent to @{username}")
            else:
                db.update_contact_status(username, "Failed", error)
                db.add_log(username, name, "Failed", error)
                self._log(f"Failed @{username}: {error}")

            if progress_callback:
                progress_callback(sent_total, total)

            # Inter-message delay
            if i < total - 1 and not stop_event.is_set():
                delay = random.randint(min_delay, max_delay)
                self._log(f"Waiting {delay}s before next message...")
                await self._interruptible_sleep(delay, stop_event)

        self._log("Campaign finished.")

    async def _send_dm(
        self, username: str, message: str, stop_event: threading.Event
    ) -> tuple[bool, str]:
        """Send one DM. Returns (success, error_msg)."""
        page = self._page
        try:
            profile_url = f"{INSTAGRAM_URL}/{username}/"
            self._log(f"  -> Visiting @{username} profile...")
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30_000)
            await self._random_wait(2, 3)

            # Session expired?
            if "login" in page.url:
                return False, "Session expired"

            # Profile not found?
            title = (await page.title()).lower()
            if "page not found" in title or "sorry" in title:
                await self._screenshot(f"not_found_{username}")
                return False, "Profile not found"

            # Click the Message button (only within the main profile content area)
            message_clicked = False
            main_area = page.locator('main, div[role="main"]')
            
            # Look for elements inside the main content area that have the EXACT text "Message"
            msg_button_locators = [
                main_area.get_by_role("button", name=re.compile(r"^Message$", re.IGNORECASE)),
                main_area.get_by_role("link", name=re.compile(r"^Message$", re.IGNORECASE)),
                main_area.locator('div[role="button"]').filter(has_text=re.compile(r"^Message$", re.IGNORECASE)),
                main_area.locator('button').filter(has_text=re.compile(r"^Message$", re.IGNORECASE)),
                main_area.locator('a').filter(has_text=re.compile(r"^Message$", re.IGNORECASE)),
            ]
            
            for loc in msg_button_locators:
                try:
                    count = await loc.count()
                    for idx in range(count):
                        item = loc.nth(idx)
                        if await item.is_visible(timeout=2_000):
                            # Try standard click first, fallback to JS click if intercepted
                            try:
                                await item.click(timeout=3_000)
                            except Exception:
                                await item.evaluate("el => el.click()")
                            message_clicked = True
                            self._log("  -> Clicked profile Message button")
                            break
                    if message_clicked:
                        break
                except Exception:
                    continue

            # If standard Message button not found, try the Options (...) menu (common on private profiles)
            if not message_clicked:
                try:
                    options_btn = None
                    for sel in [
                        'button:has(svg[aria-label*="ption" i])',
                        'div[role="button"]:has(svg[aria-label*="ption" i])',
                        'svg[aria-label*="ption" i]',
                        'button[aria-label*="ption" i]',
                    ]:
                        loc = main_area.locator(sel).first
                        if await loc.is_visible(timeout=1_000):
                            options_btn = loc
                            break
                            
                    if options_btn:
                        self._log("  -> Found Options button, clicking...")
                        await options_btn.click()
                        await self._random_wait(1.5, 2.5)
                        
                        # Wait for options dialog
                        dialog = page.locator('div[role="dialog"]').first
                        if await dialog.is_visible(timeout=3_000):
                            # Find "Send message" option in the dialog
                            for opt_sel in [
                                'button:has-text("Message")',
                                'button:has-text("Send message")',
                                'div[role="button"]:has-text("Message")',
                                'div[role="button"]:has-text("Send message")',
                            ]:
                                opt_loc = dialog.locator(opt_sel).first
                                if await opt_loc.is_visible(timeout=1_000):
                                    await opt_loc.click()
                                    message_clicked = True
                                    self._log("  -> Clicked 'Send message' from Options menu")
                                    break
                            
                            if not message_clicked:
                                # Close the dialog if we didn't find the message option
                                cancel_btn = dialog.locator('button:has-text("Cancel")').first
                                if await cancel_btn.is_visible(timeout=1_000):
                                    await cancel_btn.click()
                except Exception as e:
                    self._log(f"  -> Error trying Options menu: {e}")

            # If we clicked the button, wait up to 12s for the chat input to actually appear
            if message_clicked:
                self._log("  -> Waiting for chat input field to appear...")
                input_appeared = False
                for _ in range(12):
                    for loc in [
                        page.get_by_placeholder("Message", exact=False),
                        page.get_by_role("textbox", name="Message", exact=False),
                        page.locator('div[role="textbox"][aria-label*="essage" i]'),
                        page.locator('div[contenteditable="true"]')
                    ]:
                        try:
                            count = await loc.count()
                            for i in range(count):
                                item = loc.nth(i)
                                if await item.is_visible():
                                    html = await item.evaluate("el => el.outerHTML")
                                    if "search" not in html.lower() and "query" not in html.lower():
                                        # Only accept if it is the correct recipient's chat
                                        if await self._verify_recipient(username, item):
                                            input_appeared = True
                                            break
                            if input_appeared:
                                break
                        except Exception:
                            pass
                    if input_appeared:
                        break
                    await asyncio.sleep(1)
                
                if not input_appeared:
                    self._log("  -> WARNING: Message button clicked but chat input did not load or verify. Falling back to direct composer.")
                    message_clicked = False  # Force fallback

            if not message_clicked:
                # Fallback: use /direct/new/ composer
                self._log("  -> Navigating to direct DM composer...")
                await page.goto(INSTAGRAM_DM_NEW, wait_until="domcontentloaded", timeout=30_000)
                await self._random_wait(2, 3)

                search_input = page.locator('input[placeholder*="Search"]').first
                await search_input.wait_for(state="visible", timeout=10_000)
                await self._human_type(search_input, username)
                await self._random_wait(1, 2)

                result = page.locator(
                    f'div[role="option"]:has-text("{username}"), '
                    f'span:has-text("{username}")'
                ).first
                await result.wait_for(state="visible", timeout=8_000)
                await result.click()
                await self._random_wait(0.5, 1)

                next_btn = page.locator(
                    'div[role="button"]:has-text("Chat"), '
                    'div[role="button"]:has-text("Next")'
                ).first
                await next_btn.wait_for(state="visible", timeout=5_000)
                await next_btn.click()
                
                # Wait for the direct inbox chat to load
                self._log("  -> Waiting for direct composer chat to load...")
                await self._random_wait(2, 3)

            # Find message text input and verify recipient (with retry loop)
            self._log(f"  -> Verifying recipient is @{username}...")
            msg_input = None
            verified = False
            for _ in range(12):
                msg_input = await self._find_active_textbox()
                if msg_input:
                    if await self._verify_recipient(username, msg_input):
                        verified = True
                        break
                await asyncio.sleep(1)

            if not verified or msg_input is None:
                await self._screenshot(f"wrong_user_{username}")
                return False, f"Recipient verification failed: active chat does not belong to @{username}"

            await msg_input.click()
            await msg_input.focus()
            await self._random_wait(0.5, 1.0)

            # Type the message (human-like)
            await self._human_type_content_editable(msg_input, message)
            await self._random_wait(0.5, 2)

            # Click Send
            send_selectors = [
                'div[role="button"]:has-text("Send")',
                'button[type="submit"]:has-text("Send")',
                'button:has-text("Send")',
            ]
            sent = False
            for sel in send_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=3_000):
                        await btn.click()
                        sent = True
                        break
                except Exception:
                    continue

            if not sent:
                await msg_input.press("Enter")

            await self._random_wait(1.5, 3)
            return True, ""

        except Exception as e:
            await self._screenshot(f"error_{username}")
            return False, str(e)

    async def _find_active_textbox(self) -> any:
        """Find the active message input textbox on the page."""
        page = self._page
        
        # 1. Try Playwright's semantic locators first
        semantic_locators = [
            page.get_by_placeholder("Message", exact=False),
            page.get_by_role("textbox", name="Message", exact=False),
            page.get_by_role("textbox", name="Write a message", exact=False),
        ]
        for loc in semantic_locators:
            try:
                first_loc = loc.first
                if await first_loc.is_visible(timeout=200):
                    html = await first_loc.evaluate("el => el.outerHTML")
                    if "search" not in html.lower() and "query" not in html.lower():
                        return first_loc
            except Exception:
                continue

        # 2. Try CSS selectors
        input_selectors = [
            'div[role="textbox"][aria-label*="essage" i]',
            'div[contenteditable="true"][aria-label*="essage" i]',
            'div[contenteditable="true"][tabindex="0"]',
            'p[data-lexical-editor="true"]',
            'div[contenteditable="true"]',
            '[role="textbox"]',
        ]
        for sel in input_selectors:
            try:
                locs = page.locator(sel)
                count = await locs.count()
                for i in range(count):
                    loc = locs.nth(i)
                    if await loc.is_visible(timeout=200):
                        html = await loc.evaluate("el => el.outerHTML")
                        if "search" not in html.lower() and "query" not in html.lower():
                            return loc
            except Exception:
                continue
        return None

    async def _verify_recipient(self, username: str, textbox_locator=None) -> bool:
        """
        Verify if the currently open chat belongs to the target username.
        Returns True if verified, False otherwise.
        """
        page = self._page
        username_lower = username.lower()
        
        # 1. Direct URL check: if the URL contains the username
        if f"/direct/t/{username_lower}" in page.url.lower():
            self._log("  -> Recipient verified via URL path")
            return True
            
        # Find a visible textbox if not passed
        if textbox_locator is None:
            textbox_locator = await self._find_active_textbox()

        if not textbox_locator:
            return False

        # Evaluate recipient verification in browser context using horizontal boundary check
        try:
            verified = await textbox_locator.evaluate(
                """
                (textbox, targetUser) => {
                    const targetLower = targetUser.toLowerCase();
                    const textboxRect = textbox.getBoundingClientRect();
                    const minX = textboxRect.left - 50; // Buffer for layout alignment
                    
                    const links = document.querySelectorAll('a');
                    for (const link of links) {
                        const href = link.getAttribute('href') || '';
                        const hrefLower = href.toLowerCase();
                        if (hrefLower === `/${targetLower}/` || 
                            hrefLower === `/${targetLower}` || 
                            hrefLower.includes(`/${targetLower}/`)) {
                            
                            const linkRect = link.getBoundingClientRect();
                            // Ensure the link is visible and inside the active chat pane (to the right of minX)
                            if (linkRect.width > 0 && linkRect.height > 0 && linkRect.left >= minX) {
                                return true;
                            }
                        }
                    }
                    return false;
                }
                """,
                username_lower
            )
            return bool(verified)
        except Exception as e:
            self._log(f"  -> Recipient verification evaluation error: {e}")
            
        return False

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _human_type(self, locator, text: str) -> None:
        """Type into an <input> character by character with random delays."""
        for char in text:
            await locator.type(char, delay=random.uniform(50, 150))
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.1, 0.3))

    async def _human_type_content_editable(self, locator, text: str) -> None:
        """Type into a contenteditable div character by character."""
        for char in text:
            await locator.type(char, delay=random.uniform(50, 150))
            if random.random() < 0.04:
                await asyncio.sleep(random.uniform(0.1, 0.3))

    async def _random_wait(self, low: float, high: float) -> None:
        await asyncio.sleep(random.uniform(low, high))

    async def _interruptible_sleep(self, seconds: int, stop_event: threading.Event) -> None:
        """Sleep in 1s chunks so stop_event can interrupt quickly."""
        for _ in range(seconds):
            if stop_event.is_set():
                return
            await asyncio.sleep(1)

    async def _screenshot(self, label: str) -> None:
        try:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(SCREENSHOTS_DIR, f"{label}_{ts}.png")
            await self._page.screenshot(path=path, full_page=False)
            self._log(f"Screenshot: {path}")
        except Exception:
            pass

    def stop(self) -> None:
        self._running = False
