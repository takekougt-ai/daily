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
POST_FILE = "/tmp/generated_post.txt"

genai.configure(api_key=GEMINI_API_KEY)


def get_sheets_service():
    creds_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds)


def get_pending_memos(service):
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=GOOGLE_SHEETS_ID, range="Sheet1!A:D")
        .execute()
    )
    rows = result.get("values", [])
    pending = [
        (i + 1, row)
        for i, row in enumerate(rows)
        if len(row) >= 4 and row[3] == "pending"
    ]
    return pending


def mark_as_used(service, row_numbers):
    requests = [
        {"range": f"Sheet1!D{n}", "values": [["used"]]} for n in row_numbers
    ]
    if requests:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=GOOGLE_SHEETS_ID,
            body={"valueInputOption": "USER_ENTERED", "data": requests},
        ).execute()


def load_system_prompt():
    with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


def generate_post(memos_text):
    system_prompt = load_system_prompt()
    now = datetime.now(JST)
    time_context = f"現在時刻: {now.strftime('%Y-%m-%d %H:%M')} JST"

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_prompt,
    )
    response = model.generate_content(
        f"{time_context}\n\n以下のメモから1つのSNS投稿文を作成してください:\n\n{memos_text}"
    )
    return response.text


def main():
    service = get_sheets_service()
    pending = get_pending_memos(service)

    if not pending:
        print("No pending memos. Skipping post generation.")
        with open(POST_FILE, "w") as f:
            f.write("")
        return

    # 最新の最大3件を使用
    selected = pending[-3:]
    memos_text = "\n".join([f"- {row[2]}" for _, row in selected])
    row_numbers = [row_num for row_num, _ in selected]

    print(f"Generating post from {len(selected)} memos...")
    post_text = generate_post(memos_text)

    with open(POST_FILE, "w", encoding="utf-8") as f:
        f.write(post_text)

    mark_as_used(service, row_numbers)
    print(f"Generated post:\n{post_text}")


if __name__ == "__main__":
    main()
