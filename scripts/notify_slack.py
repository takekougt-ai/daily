import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_NOTIFY_CHANNEL_ID = os.environ["SLACK_NOTIFY_CHANNEL_ID"]
POST_FILE = "/tmp/generated_post.txt"


def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def main():
    post_text = read_file(POST_FILE)
    if not post_text:
        print("No post text. Skipping Slack notification.")
        return

    x_post_id = read_file("/tmp/x_post_id.txt")
    threads_post_id = read_file("/tmp/threads_post_id.txt")

    message = f"✅ 投稿完了\n\n*投稿内容:*\n{post_text}"

    if x_post_id:
        message += f"\n\n*X:* https://x.com/i/web/status/{x_post_id}"
    if threads_post_id:
        message += f"\n\n*Threads ID:* {threads_post_id}"

    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        client.chat_postMessage(channel=SLACK_NOTIFY_CHANNEL_ID, text=message)
        print("Slack notification sent")
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}")


if __name__ == "__main__":
    main()
