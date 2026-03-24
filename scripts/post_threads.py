import os

import requests

THREADS_ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
THREADS_USER_ID = os.environ["THREADS_USER_ID"]
POST_FILE = "/tmp/generated_post.txt"
THREADS_API_BASE = "https://graph.threads.net/v1.0"


def create_container(text):
    url = f"{THREADS_API_BASE}/{THREADS_USER_ID}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()["id"]


def publish_container(container_id):
    url = f"{THREADS_API_BASE}/{THREADS_USER_ID}/threads_publish"
    params = {
        "creation_id": container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()["id"]


def main():
    with open(POST_FILE, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        print("No post text. Skipping Threads post.")
        return

    container_id = create_container(text)
    post_id = publish_container(container_id)
    print(f"Posted to Threads: {post_id}")

    with open("/tmp/threads_post_id.txt", "w") as f:
        f.write(str(post_id))


if __name__ == "__main__":
    main()
