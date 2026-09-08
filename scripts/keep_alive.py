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

from playwright.sync_api import sync_playwright

# スリープ画面の復帰ボタン（文言は Streamlit 側の変更に備えて緩めに一致させる）
WAKE_BUTTON_PATTERN = re.compile(r"get this app back up", re.IGNORECASE)
# アプリ本体が描画されたと判断するセレクタ
# 注意: *.streamlit.app はアプリ本体を iframe 内に描画するため、
# メインフレームだけでなく全フレームを走査して探す必要がある。
APP_SELECTOR = '[data-testid="stAppViewContainer"], [data-testid="stApp"]'

WAKE_TIMEOUT_MS = int(os.environ.get("KEEP_ALIVE_WAKE_TIMEOUT_MS", "180000"))
LINGER_SECONDS = int(os.environ.get("KEEP_ALIVE_LINGER_SECONDS", "15"))


def log(message: str) -> None:
    print(f"[keep-alive] {message}", flush=True)


def app_is_rendered(page) -> bool:
    """全フレームを走査してアプリ本体のコンテナが存在するか調べる。"""
    for frame in page.frames:
        try:
            if frame.query_selector(APP_SELECTOR):
                return True
        except Exception:
            # ナビゲーション中に frame がデタッチされることがあるので無視して続行
            continue
    return False


def click_wake_button(page) -> bool:
    """スリープ画面の復帰ボタンを全フレームから探してクリックする。"""
    for frame in page.frames:
        try:
            button = frame.get_by_role("button", name=WAKE_BUTTON_PATTERN)
            if button.count() > 0:
                button.first.click()
                return True
        except Exception:
            continue
    return False


def keep_alive(url: str) -> bool:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            log(f"open {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(5_000)

            if click_wake_button(page):
                log("app is sleeping -> clicked wake button")
            else:
                log("wake button not found (app is probably awake)")

            deadline = time.monotonic() + WAKE_TIMEOUT_MS / 1000
            while not app_is_rendered(page):
                if time.monotonic() >= deadline:
                    log("ERROR: app did not render within timeout")
                    return False
                page.wait_for_timeout(2_000)

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
