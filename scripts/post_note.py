import json
import os
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

NOTE_EMAIL = os.environ["NOTE_EMAIL"]
NOTE_PASSWORD = os.environ["NOTE_PASSWORD"]
ARTICLE_FILE = "/tmp/note_article.json"


def load_article():
    with open(ARTICLE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def post_to_note(title, body):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1280,800",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ja-JP",
        )
        # webdriverプロパティを隐薔
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        page = context.new_page()
        page.set_default_timeout(60000)

        print("[Note] Navigating to login page...")
        page.goto("https://note.com/login")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        print(f"[Note] Login page URL: {page.url}")

        # メール入力（idで直指定）
        page.wait_for_selector("input#email", timeout=10000)
        page.click("input#email")
        time.sleep(0.5)
        page.fill("input#email", NOTE_EMAIL)
        print("[Note] Filled email")

        # パスワード入力
        page.wait_for_selector("input#password", timeout=10000)
        page.click("input#password")
        time.sleep(0.5)
        page.fill("input#password", NOTE_PASSWORD)
        print("[Note] Filled password")

        # ログインボタンをクリック
        page.click('button:has-text("ログイン")')
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        print(f"[Note] After login URL: {page.url}")

        # ログイン失敗のチェック
        if "login" in page.url:
            error_text = page.locator(".error, [class*='error'], [class*='alert']").all_text_contents()
            print(f"[Note] Login failed. Error messages: {error_text}")
            print(f"[Note] Page title: {page.title()}")
            raise RuntimeError(f"Login failed. Still on login page. Errors: {error_text}")

        print("[Note] Login successful!")

        # 新規記事作成ページ
        page.goto("https://note.com/notes/new")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        print(f"[Note] Editor URL: {page.url}")

        if "login" in page.url:
            raise RuntimeError("Redirected to login page. Session not maintained.")

        # タイトル入力
        title_selectors = [
            'textarea[placeholder="記事タイトル"]',
            '[data-placeholder="記事タイトル"]',
            'h1[contenteditable]',
            'div[contenteditable][data-placeholder]',
        ]
        for sel in title_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.click(sel)
                if "textarea" in sel:
                    page.fill(sel, title)
                else:
                    page.type(sel, title)
                print(f"[Note] Filled title: {sel}")
                break
            except PlaywrightTimeoutError:
                print(f"[Note] Title selector not found: {sel}")
        else:
            print("[Note] Dumping editor HTML:")
            print(page.content()[:3000])
            raise RuntimeError("Title input not found")

        # 本文入力
        for sel in [".ProseMirror", '[contenteditable="true"]']:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.click(sel)
                page.evaluate(
                    "(sel, text) => { const el = document.querySelector(sel); "
                    "if (el) { el.innerText = text; "
                    "el.dispatchEvent(new Event('input', {bubbles: true})); } }",
                    sel, body,
                )
                print(f"[Note] Filled body: {sel}")
                break
            except PlaywrightTimeoutError:
                print(f"[Note] Body selector not found: {sel}")
        else:
            raise RuntimeError("Body input not found")

        time.sleep(2)

        # 公開
        for sel in [
            'button:has-text("公開設定へ")',
            'button:has-text("投稿")',
            'button:has-text("公開")',
        ]:
            try:
                page.click(sel, timeout=5000)
                print(f"[Note] Clicked publish: {sel}")
                break
            except PlaywrightTimeoutError:
                pass

        page.wait_for_load_state("networkidle")
        time.sleep(3)

        confirm_btn = page.locator('button:has-text("公開する")')
        if confirm_btn.count() > 0:
            confirm_btn.first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(3)

        current_url = page.url
        print(f"[Note] Published URL: {current_url}")
        with open("/tmp/note_post_url.txt", "w") as f:
            f.write(current_url)

        browser.close()
        return current_url


def main():
    article = load_article()
    if not article:
        print("No article data. Skipping Note post.")
        sys.exit(0)

    title = article.get("title", "")
    body = article.get("body", "")
    if not title or not body:
        print("Missing title or body. Skipping Note post.")
        sys.exit(0)

    print(f"[Note] Posting article: {title}")
    url = post_to_note(title, body)
    print(f"[Note] Done: {url}")


if __name__ == "__main__":
    main()
