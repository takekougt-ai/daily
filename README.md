# SNS Auto Post Bot

Slackに一行メモを送るだけで、Claude APIが投稿文を生成してX（Twitter）とThreadsに自動投稿するシステム。

## アーキテクチャ

```
Slack #post-memo にメモ送信
        ↓
GitHub Actions (毎時実行)
        ↓
slack_to_sheets.py → Google Sheets にメモを蓄積
        ↓
    [7:00 / 12:00 / 19:00 JST のみ]
        ↓
generate_post.py → Claude API で投稿文生成
        ↓
post_x.py        → X に投稿
post_threads.py  → Threads に投稿
        ↓
notify_slack.py  → Slack に完了通知
```

## セットアップ

### 1. GitHub Secrets の登録

Settings → Secrets and variables → Actions に以下を登録。

| Secret名 | 説明 |
|---|---|
| `SLACK_BOT_TOKEN` | Slack Bot の OAuth トークン (`xoxb-...`) |
| `SLACK_CHANNEL_ID` | #post-memo チャンネルのID |
| `SLACK_NOTIFY_CHANNEL_ID` | 完了通知を送るSlackチャンネルのID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google サービスアカウントのJSONキー（文字列全体） |
| `GOOGLE_SHEETS_ID` | Google SheetsのID（URLの `/d/〜/edit` の部分） |
| `ANTHROPIC_API_KEY` | Anthropic APIキー |
| `X_API_KEY` | X (Twitter) API Key |
| `X_API_SECRET` | X (Twitter) API Secret |
| `X_ACCESS_TOKEN` | X (Twitter) Access Token |
| `X_ACCESS_TOKEN_SECRET` | X (Twitter) Access Token Secret |
| `THREADS_ACCESS_TOKEN` | Threads API Access Token |
| `THREADS_USER_ID` | Threads のユーザーID |

### 2. Slack Bot の設定

Slack App に以下のスコープを付与:
- `channels:history`
- `channels:read`
- `chat:write`

Bot を `#post-memo` チャンネルと通知チャンネルにInviteする。

### 3. Google Sheets の準備

1. 新規スプレッドシートを作成
2. Sheet1 のA〜D列に以下のデータが蓄積される:
   - A列: `timestamp` (Slackのts)
   - B列: `datetime` (JST)
   - C列: `text` (メモ内容)
   - D列: `status` (`pending` / `used`)
3. サービスアカウントにスプレッドシートの編集権限を付与

### 4. 動作確認

GitHub Actions の `Actions` タブから手動実行 (`workflow_dispatch`)。
`force_post` を `true` にすると投稿時間に関係なくテスト投稿できる。

## 使い方

Slack の `#post-memo` チャンネルに一行送るだけ。

```
今日キーエンスで詰められた
GitHub Actionsのcronがまたハマった
犬が散歩拒否した
AIで3時間かかってた作業が5分になった
```

あとは全部自動で処理される。

## 投稿スケジュール

| 時間 | 処理 |
|---|---|
| 毎時0分 | Slackメモ → Google Sheetsへ同期 |
| 7:00 JST | 投稿生成 → X/Threads 投稿 → Slack通知 |
| 12:00 JST | 投稿生成 → X/Threads 投稿 → Slack通知 |
| 19:00 JST | 投稿生成 → X/Threads 投稿 → Slack通知 |
