import os
import json
from datetime import datetime, timezone, timedelta

import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
GOOGLE_SHEETS_ID = os.environ["GOOGLE_SHEETS_ID"]

JST = timezone(timedelta(hours=9))
ARTICLE_FILE = "/tmp/note_article.json"

genai.configure(api_key=GEMINI_API_KEY)


def get_sheets_service():
    creds_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def get_weekly_memos(service):
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=GOOGLE_SHEETS_ID, range="Sheet1!A:D")
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

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_prompt,
    )
    response = model.generate_content(
        f"期間: {week_str}\n\n今週のメモ一覧:\n{memos_text}\n\n"
        "これらのメモをもとにnote記事を作成してください。"
    )

    raw = response.text.strip()
    # JSON部分だけ抽出
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return json.loads(raw[start:end])


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
