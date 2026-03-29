import json
import os
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

NOTE_AUTH_TOKEN = os.environ["NOTE_AUTH_TOKEN"]
ARTICLE_FILE = "/tmp/note_article.json"


def load_article():
    with open(ARTICLE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def post_to_note(title, body):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
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
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        # Cookieで直接認証（ログインフォーム不要）
        context.add_cookies([
            {
                "name": "note_gql_auth_token",
                "value": NOTE_AUTH_TOKEN,
                "domain": ".note.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }
        ])

        page = context.new_page()
        page.set_default_timeout(60000)

        # 認証確認
        print("[Note] Checking auth...")
        page.goto("https://note.com")
        page.wait_for_load_state("networkidle")
        print(f"[Note] Top page URL: {page.url}")

        # 新規記事作成ページ
        page.goto("https://note.com/notes/new")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        print(f"[Note] Editor URL: {page.url}")

        if "login" in page.url:
            raise RuntimeError(
                "Redirected to login. NOTE_AUTH_TOKEN may be expired. "
                "Please refresh the cookie from your browser."
            )

        # タイトル入力
        for sel in [
            'textarea[placeholder="記事タイトル"]',
            '[data-placeholder="記事タイトル"]',
            'h1[contenteditable]',
            'div[contenteditable][data-placeholder]',
        ]:
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
