import os
import json
from datetime import datetime, timezone, timedelta

from google import genai
from google.genai import types
from google.oauth2 import service_account
from googleapiclient.discovery import build

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
GOOGLE_SHEETS_ID = os.environ["GOOGLE_SHEETS_ID"]

JST = timezone(timedelta(hours=9))
ARTICLE_FILE = "/tmp/note_article.json"

client = genai.Client(api_key=GEMINI_API_KEY)


def get_sheets_service():
    creds_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def get_first_sheet_name(service):
    meta = service.spreadsheets().get(spreadsheetId=GOOGLE_SHEETS_ID).execute()
    return meta["sheets"][0]["properties"]["title"]


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
    return memos


def load_system_prompt():
    with open("prompts/note_article_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


def generate_article(memos):
    system_prompt = load_system_prompt()
    now = datetime.now(JST)
    week_str = now.strftime("%Y年%m月第%W週")
    memos_text = "\n".join([f"- {m}" for m in memos])

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=(
            f"期間: {week_str}\n\n今週のメモ一覧:\n{memos_text}\n\n"
            "これらのメモをもとにnote記事を作成してください。"
        ),
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=2048,
            response_mime_type="application/json",
        ),
    )

    raw = response.text.strip()
    print(f"[Gemini] Raw response preview: {raw[:200]}")
    return json.loads(raw)


def main():
    service = get_sheets_service()
    memos = get_weekly_memos(service)

    if not memos:
        print("No memos this week. Skipping article generation.")
        with open(ARTICLE_FILE, "w") as f:
            json.dump({}, f)
        return

    print(f"Generating article from {len(memos)} memos...")
    article = generate_article(memos)

    with open(ARTICLE_FILE, "w", encoding="utf-8") as f:
        json.dump(article, f, ensure_ascii=False, indent=2)

    print(f"Title: {article['title']}")
    print(f"Body preview: {article['body'][:100]}...")


if __name__ == "__main__":
    main()
