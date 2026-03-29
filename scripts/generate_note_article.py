import os
import json
import time
from datetime import datetime, timezone, timedelta

import httplib2
from google import genai
from google.genai import types
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import google_auth_httplib2
from googleapiclient.discovery import build

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
GOOGLE_SHEETS_ID = os.environ["GOOGLE_SHEETS_ID"]

JST = timezone(timedelta(hours=9))
ARTICLE_FILE = "/tmp/note_article.json"
MAX_MEMOS = 20

client = genai.Client(api_key=GEMINI_API_KEY)


def get_sheets_service():
    creds_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    creds.refresh(Request())
    http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http(timeout=30))
    return build("sheets", "v4", http=http)


def get_first_sheet_name(service):
    for attempt in range(3):
        try:
            meta = service.spreadsheets().get(spreadsheetId=GOOGLE_SHEETS_ID).execute()
            return meta["sheets"][0]["properties"]["title"]
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                print(f"[Sheets] Retry {attempt+1}/3 after {wait}s: {e}")
                time.sleep(wait)
            else:
                raise


def get_weekly_memos(service):
    sheet = get_first_sheet_name(service)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=GOOGLE_SHEETS_ID, range=f"{sheet}!A:D")
        .execute()
    )
    rows = result.get("values", [])

    one_week_ago = datetime.now(JST) - timedelta(days=7)
    memos = []
    for row in rows:
        if len(row) < 3:
            continue
        try:
            dt = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
        except (ValueError, IndexError):
            continue
        if dt >= one_week_ago:
            memos.append(row[2])
    return memos[-MAX_MEMOS:]


def load_system_prompt():
    with open("prompts/note_article_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


def generate_title_and_body(memos):
    system_prompt = load_system_prompt()
    now = datetime.now(JST)
    week_str = now.strftime("%Y年%m月第%W週")
    memos_text = "\n".join([f"- {m}" for m in memos])

    # タイトルと本文を分けて生成することでJSON切れを回避
    title_resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"期間: {week_str}\nメモ: {memos_text}\n\n記事タイトルのみ30字以内で生成してください。実際のタイトル文字列のみ出力。",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=100,
        ),
    )
    title = (title_resp.text or "").strip().strip('"')
    print(f"[Gemini] Title: {title}")

    body_resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=(
            f"期間: {week_str}\nメモ: {memos_text}\n\n"
            f"タイトル「{title}」の本文をMarkdown形式で600字以内で生成してください。"
            "本文のみ出力。JSON不要。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=2048,
        ),
    )
    body = (body_resp.text or "").strip()
    finish = body_resp.candidates[0].finish_reason if body_resp.candidates else "unknown"
    print(f"[Gemini] Body ({len(body)} chars, finish_reason={finish})")

    return title, body


def main():
    service = get_sheets_service()
    memos = get_weekly_memos(service)

    if not memos:
        print("No memos this week. Skipping article generation.")
        with open(ARTICLE_FILE, "w") as f:
            json.dump({}, f)
        return

    print(f"Generating article from {len(memos)} memos...")
    title, body = generate_title_and_body(memos)

    if not title or not body:
        raise RuntimeError(f"Empty response from Gemini. title={bool(title)}, body={bool(body)}")

    article = {"title": title, "body": body}
    with open(ARTICLE_FILE, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)

    print(f"Title: {article['title']}")
    print(f"Body preview: {article['body'][:100]}...")


if __name__ == "__main__":
    main()
