"""Streamlit Community Cloud のアプリを起こして、スリープさせないためのスクリプト。

Streamlit Community Cloud は一定時間アクセスがないとアプリをスリープさせる。
単純な HTTP GET では静的な HTML が 200 で返るだけで Python 側は起動しないため、
ヘッドレスブラウザで実際にページを開き、必要ならスリープ画面の
「Yes, get this app back up!」ボタンを押してアプリが描画されるまで待つ。

使い方:
    STREAMLIT_APP_URL=https://xxx.streamlit.app python scripts/keep_alive.py
"""

import os
import re
import sys
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

# スリープ画面の復帰ボタン（文言は Streamlit 側の変更に備えて緩めに一致させる）
WAKE_BUTTON_PATTERN = re.compile(r"get this app back up", re.IGNORECASE)
# アプリ本体が描画されたと判断するセレクタ
APP_SELECTOR = '[data-testid="stAppViewContainer"], [data-testid="stApp"]'

WAKE_TIMEOUT_MS = int(os.environ.get("KEEP_ALIVE_WAKE_TIMEOUT_MS", "180000"))
LINGER_SECONDS = int(os.environ.get("KEEP_ALIVE_LINGER_SECONDS", "15"))


def log(message: str) -> None:
    print(f"[keep-alive] {message}", flush=True)


def keep_alive(url: str) -> bool:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            log(f"open {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(5_000)

            wake_button = page.get_by_role("button", name=WAKE_BUTTON_PATTERN)
            if wake_button.count() > 0:
                log("app is sleeping -> click wake button")
                wake_button.first.click()
            else:
                log("wake button not found (app is probably awake)")

            try:
                page.wait_for_selector(APP_SELECTOR, timeout=WAKE_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                log("ERROR: app did not render within timeout")
                return False

            log(f"app rendered; linger {LINGER_SECONDS}s so the visit is counted")
            time.sleep(LINGER_SECONDS)
            return True
        finally:
            browser.close()


def main() -> int:
    url = os.environ.get("STREAMLIT_APP_URL", "").strip()
    if not url:
        log("ERROR: STREAMLIT_APP_URL is not set")
        return 2
    return 0 if keep_alive(url) else 1


if __name__ == "__main__":
    sys.exit(main())
