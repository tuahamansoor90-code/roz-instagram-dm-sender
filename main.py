"""
main.py - Entry point for Instagram DM Sender
"""

import subprocess
import sys
import os
import warnings

# Suppress the cosmetic "I/O operation on closed pipe" ResourceWarnings
# that appear during subprocess cleanup. These are harmless GC noise.
warnings.filterwarnings("ignore", category=ResourceWarning)


def ensure_playwright_browser():
    """Install Chromium browser if not already installed."""
    print("Checking Playwright Chromium installation...")
    try:
        import sys
        from playwright.__main__ import main as playwright_main
        
        # Save original sys.argv and override for playwright CLI
        old_argv = sys.argv
        sys.argv = ["playwright", "install", "chromium"]
        try:
            playwright_main()
        except SystemExit as e:
            if e.code == 0:
                print("Chromium ready.")
            else:
                print(f"Playwright installation exited with code: {e.code}")
        finally:
            sys.argv = old_argv
    except Exception as e:
        print(f"Could not auto-install Chromium: {e}")
        print("Please run manually:  python -m playwright install chromium")


def main():
    # Verify or activate product license before launching
    from license_verifier import verify_or_activate_license
    if not verify_or_activate_license():
        sys.exit(0)

    ensure_playwright_browser()

    # Create helper directories
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base, "screenshots"),       exist_ok=True)
    os.makedirs(os.path.join(base, "instagram_session"), exist_ok=True)

    # Launch the GUI
    from ui import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
