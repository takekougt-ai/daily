import os
import json
from datetime import datetime, timezone, timedelta

from slack_sdk import WebClient
from google.oauth2 import service_account
from googleapiclient.discovery import build

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
GOOGLE_SHEETS_ID = os.environ["GOOGLE_SHEETS_ID"]

JST = timezone(timedelta(hours=9))
FETCH_DAYS = 7  # 取得対象期間（日）


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


def get_existing_timestamps(service):
    sheet = get_first_sheet_name(service)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=GOOGLE_SHEETS_ID, range=f"{sheet}!A:A")
        .execute()
    )
    values = result.get("values", [])
    return {row[0] for row in values if row}


def fetch_slack_messages():
    client = WebClient(token=SLACK_BOT_TOKEN)
    oldest = (datetime.now(timezone.utc) - timedelta(days=FETCH_DAYS)).timestamp()
    messages = []
    cursor = None

    while True:
        kwargs = {"channel": SLACK_CHANNEL_ID, "oldest": str(oldest), "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        response = client.conversations_history(**kwargs)
        messages.extend(response["messages"])
        if not response.get("response_metadata", {}).get("next_cursor"):
            break
        cursor = response["response_metadata"]["next_cursor"]

    return messages


def append_to_sheets(service, rows):
    if not rows:
        return
    sheet = get_first_sheet_name(service)
    service.spreadsheets().values().append(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=f"{sheet}!A:D",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()


def main():
    service = get_sheets_service()
    existing_ts = get_existing_timestamps(service)
    messages = fetch_slack_messages()

    new_rows = []
    for msg in messages:
        ts = msg.get("ts", "")
        if ts in existing_ts:
            continue
        text = msg.get("text", "").strip()
        if not text or msg.get("subtype"):
            continue

        dt = datetime.fromtimestamp(float(ts), tz=JST)
        new_rows.append([
            ts,
            dt.strftime("%Y-%m-%d %H:%M:%S"),
            text,
            "pending",
        ])

    if new_rows:
        append_to_sheets(service, new_rows)
        print(f"Added {len(new_rows)} new memos to Sheets")
    else:
        print("No new memos (all already synced or no messages in past {FETCH_DAYS} days)")


if __name__ == "__main__":
    main()
