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
POST_FILE = "/tmp/generated_post.txt"

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


def get_pending_memos(service):
    sheet = get_first_sheet_name(service)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=GOOGLE_SHEETS_ID, range=f"{sheet}!A:D")
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
    sheet = get_first_sheet_name(service)
    requests = [
        {"range": f"{sheet}!D{n}", "values": [["used"]]} for n in row_numbers
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

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{time_context}\n\n以下のメモから1つのSNS投稿文を作成してください:\n\n{memos_text}",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=1024,
        ),
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
