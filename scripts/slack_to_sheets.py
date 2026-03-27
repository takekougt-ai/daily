import os
import json
from datetime import datetime, timezone, timedelta

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from google.oauth2 import service_account
from googleapiclient.discovery import build

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
GOOGLE_SHEETS_ID = os.environ["GOOGLE_SHEETS_ID"]

JST = timezone(timedelta(hours=9))
FETCH_DAYS = 7


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

    # チャンネル情報をデバッグ出力
    try:
        info = client.conversations_info(channel=SLACK_CHANNEL_ID)
        ch = info["channel"]
        print(f"[Slack] Channel: #{ch['name']} (id={ch['id']}, is_member={ch.get('is_member', '?')}")
    except SlackApiError as e:
        print(f"[Slack] conversations_info error: {e.response['error']}")

    oldest = (datetime.now(timezone.utc) - timedelta(days=FETCH_DAYS)).timestamp()
    messages = []
    cursor = None

    try:
        while True:
            kwargs = {"channel": SLACK_CHANNEL_ID, "oldest": str(oldest), "limit": 200}
            if cursor:
                kwargs["cursor"] = cursor
            response = client.conversations_history(**kwargs)
            messages.extend(response["messages"])
            print(f"[Slack] Fetched {len(response['messages'])} messages (total so far: {len(messages)})")
            if not response.get("response_metadata", {}).get("next_cursor"):
                break
            cursor = response["response_metadata"]["next_cursor"]
    except SlackApiError as e:
        print(f"[Slack] conversations_history error: {e.response['error']}")
        raise

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
    print(f"[Sheets] Existing timestamps: {len(existing_ts)}")

    messages = fetch_slack_messages()
    print(f"[Slack] Total messages fetched: {len(messages)}")

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

    print(f"[Sheets] New rows to add: {len(new_rows)}")
    if new_rows:
        append_to_sheets(service, new_rows)
        print(f"[Sheets] Added {len(new_rows)} new memos")
    else:
        print("[Sheets] Nothing to add")


if __name__ == "__main__":
    main()
