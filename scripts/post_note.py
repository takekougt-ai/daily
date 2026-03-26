import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

NOTE_EMAIL = os.environ["NOTE_EMAIL"]
NOTE_PASSWORD = os.environ["NOTE_PASSWORD"]
ARTICLE_FILE = "/tmp/note_article.json"
NOTE_POST_ID_FILE = "/tmp/note_post_id.txt"


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

        # ログイン
        page.goto("https://note.com/login")
        page.wait_for_load_state("networkidle")

        page.fill('input[name="email"]', NOTE_EMAIL)
        page.fill('input[name="password"]', NOTE_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 新規記事作成ページへ
        page.goto("https://note.com/notes/new")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # タイトル入力
        title_selector = 'textarea[placeholder="記事タイトル"], [data-placeholder="記事タイトル"], .title'
        page.wait_for_selector(title_selector, timeout=10000)
        page.click(title_selector)
        page.fill(title_selector, title)

        # 本文入力（contenteditable）
        body_selector = '.ProseMirror, [contenteditable="true"].editor__body, .note-editor__body'
        page.wait_for_selector(body_selector, timeout=10000)
        page.click(body_selector)
        # JavaScriptでテキストを設定してから入力イベントを発火
        page.evaluate(
            "(sel, text) => { "
            "  const el = document.querySelector(sel); "
            "  if (el) { el.innerText = text; "
            "    el.dispatchEvent(new Event('input', {bubbles: true})); } "
            "}",
            body_selector,
            body,
        )
        time.sleep(1)

        # 公開ボタン
        publish_btn = page.locator('button:has-text("公開設定へ"), button:has-text("投稿")')
        publish_btn.first.click()
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 公開確認ダイアログ
        confirm_btn = page.locator('button:has-text("公開する")')
        if confirm_btn.count() > 0:
            confirm_btn.first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(3)

        # 投稿後のURLからIDを取得
        current_url = page.url
        print(f"Published URL: {current_url}")

        with open(NOTE_POST_ID_FILE, "w") as f:
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

    url = post_to_note(title, body)
    print(f"Posted to Note: {url}")


if __name__ == "__main__":
    main()
