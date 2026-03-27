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
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.set_default_timeout(60000)

        # ログインページ
        print("[Note] Navigating to login page...")
        page.goto("https://note.com/login")
        page.wait_for_load_state("networkidle")
        print(f"[Note] Login page URL: {page.url}")

        # メール入力（複数のセレクタを試行）
        email_selectors = [
            'input[name="email"]',
            'input[type="email"]',
            'input[placeholder*="メール"]',
            'input[placeholder*="mail"]',
        ]
        for sel in email_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.fill(sel, NOTE_EMAIL)
                print(f"[Note] Filled email with selector: {sel}")
                break
            except PlaywrightTimeoutError:
                continue
        else:
            print("[Note] Could not find email input. Page content:")
            print(page.content()[:2000])
            raise RuntimeError("Email input not found")

        # パスワード入力
        password_selectors = [
            'input[name="password"]',
            'input[type="password"]',
        ]
        for sel in password_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.fill(sel, NOTE_PASSWORD)
                print(f"[Note] Filled password with selector: {sel}")
                break
            except PlaywrightTimeoutError:
                continue
        else:
            raise RuntimeError("Password input not found")

        # ログインボタン
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("ログイン")',
            'input[type="submit"]',
        ]
        for sel in submit_selectors:
            try:
                page.click(sel, timeout=5000)
                print(f"[Note] Clicked submit with selector: {sel}")
                break
            except PlaywrightTimeoutError:
                continue

        page.wait_for_load_state("networkidle")
        time.sleep(3)
        print(f"[Note] After login URL: {page.url}")

        # 新規記事作成
        page.goto("https://note.com/notes/new")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        print(f"[Note] Editor URL: {page.url}")

        # タイトル入力
        title_selectors = [
            'textarea[placeholder="記事タイトル"]',
            '[data-placeholder="記事タイトル"]',
            'h1[contenteditable]',
            '.title-input',
        ]
        for sel in title_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.click(sel)
                page.fill(sel, title) if 'textarea' in sel or 'input' in sel else page.type(sel, title)
                print(f"[Note] Filled title with selector: {sel}")
                break
            except PlaywrightTimeoutError:
                continue
        else:
            print("[Note] Could not find title input. Dumping page content:")
            print(page.content()[:2000])
            raise RuntimeError("Title input not found")

        # 本文入力
        body_selectors = [
            '.ProseMirror',
            '[contenteditable="true"]',
            '.note-editor__body',
        ]
        for sel in body_selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                page.click(sel)
                page.evaluate(
                    "(sel, text) => { "
                    "  const el = document.querySelector(sel); "
                    "  if (el) { el.innerText = text; "
                    "    el.dispatchEvent(new Event('input', {bubbles: true})); } "
                    "}",
                    sel, body,
                )
                print(f"[Note] Filled body with selector: {sel}")
                break
            except PlaywrightTimeoutError:
                continue
        else:
            raise RuntimeError("Body input not found")

        time.sleep(2)

        # 公開ボタン
        publish_btn = page.locator('button:has-text("公開設定へ"), button:has-text("投稿"), button:has-text("公開")')
        publish_btn.first.click()
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # 公開確認ダイアログ
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
