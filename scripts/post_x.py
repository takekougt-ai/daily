import os

import tweepy

X_API_KEY = os.environ["X_API_KEY"]
X_API_SECRET = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_TOKEN_SECRET = os.environ["X_ACCESS_TOKEN_SECRET"]
POST_FILE = "/tmp/generated_post.txt"


def main():
    with open(POST_FILE, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        print("No post text. Skipping X post.")
        return

    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
    )

    response = client.create_tweet(text=text)
    post_id = response.data["id"]
    print(f"Posted to X: {post_id}")

    with open("/tmp/x_post_id.txt", "w") as f:
        f.write(str(post_id))


if __name__ == "__main__":
    main()
