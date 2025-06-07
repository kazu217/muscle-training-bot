# -*- coding: utf-8 -*-
"""LINE Bot main server (Render)
--------------------------------------------------
機能:
1. 画像/動画を受信すると大学サーバー(API)へ user_id と日付を POST（重複投稿なら duplicate_with も送る）
2. 固定フレーズ応答
3. 「<名前>途中経過」で今月の忘れ回数を返信
4. `/` に "LINE bot is alive" を返す
"""

import csv
import json
import os
import hashlib
from datetime import datetime, timezone, timedelta
from linebot.exceptions import LineBotApiError
import requests
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    ImageMessage, VideoMessage, MessageEvent,
    TextMessage, TextSendMessage
)

# --------------------------------------------------
# 定数・ファイルパス
# --------------------------------------------------
PROCESSED_IDS_PATH = "processed_event_ids.json"
HASH_LOG_PATH = "hash_log.json"
LOG_PATH = "log.json"
MEMBERS_PATH = "members.json"
DAILY_CSV_PATH = "daily.csv"

# --------------------------------------------------
# 環境変数
# --------------------------------------------------
load_dotenv()
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_GROUP_ID = "C1d9ed412f2141da57e47bd28cec532a4"
UNIV_SERVER_ENDPOINT = "https://e111-131-113-97-12.ngrok-free.app/record"

# --------------------------------------------------
# 初期化
# --------------------------------------------------
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

for path, default in [
    (HASH_LOG_PATH, {}),
    (LOG_PATH, {}),
    (PROCESSED_IDS_PATH, [])
]:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)

# --------------------------------------------------
# Webhookエンドポイント
# --------------------------------------------------
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("❌ Webhook handling error:", e)
        abort(400)
    return "OK"

# --------------------------------------------------
# メディア処理（画像・動画）
# --------------------------------------------------
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
        print("👥 対象外のグループからのメディア → 無視")
        return
    if event.message.content_provider.type != "line":
        print("❌ 外部メディアなので無視")
        return

    message_id = event.message.id
    with open(PROCESSED_IDS_PATH, "r", encoding="utf-8") as f:
        processed_ids = json.load(f)
    if message_id in processed_ids:
        print(f"🔁 {message_id} はすでに処理済み → スキップ")
        return

    user_id = event.source.user_id
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
    print(f"📸 {today} に {user_id} が画像/動画を送信")

    content = line_bot_api.get_message_content(message_id).content
    if len(content) < 100:
        print("⚠️ メディアが小さすぎるため無視")
        return

    content_hash = hashlib.sha256(content).hexdigest()

    with open(HASH_LOG_PATH, "r", encoding="utf-8") as f:
        hash_log = json.load(f)
    user_hashes = hash_log.get(user_id, {})

    with open(MEMBERS_PATH, "r", encoding="utf-8") as f:
        id_to_name = json.load(f)
    name = id_to_name.get(user_id, user_id)

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)
    if name not in logs:
        logs[name] = []

    already_recorded_today = any(
        (entry == today or (isinstance(entry, dict) and entry.get("date") == today))
        for entry in logs[name]
    )
    if already_recorded_today:
        print(f"⚠️ {name} は {today} にすでに投稿済み。記録をスキップします。")
        safe_reply("すでに今日の投稿は受け取っています！", event)
        return

    if content_hash in user_hashes:
        duplicated_date = user_hashes[content_hash]
        print(f"⚠️ 重複画像/動画。{duplicated_date} の投稿と一致")
        logs[name].append(f"重複: {duplicated_date}")
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        try:
            requests.post(UNIV_SERVER_ENDPOINT, json={
                "user_id": user_id,
                "date": today,
                "duplicate": True,
                "duplicate_with": duplicated_date
            })
        except Exception as e:
            print("❌ 重複通知失敗", e)
        safe_reply(f"⚠️ 重複画像/動画。{duplicated_date} の投稿と一致", event)
        return

    user_hashes[content_hash] = today
    hash_log[user_id] = user_hashes
    with open(HASH_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(hash_log, f, ensure_ascii=False, indent=2)

    logs[name].append(now_iso)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

    try:
        res = requests.post(UNIV_SERVER_ENDPOINT, json={
            "user_id": user_id,
            "date": today
        })
        print("✅ 大学サーバーに送信成功", res.status_code)
        safe_reply("受け取りました！", event)
    except Exception as e:
        print("❌ 大学サーバーへの送信失敗", e)
        safe_reply("⚠️ エラー：記録に失敗しました。時間をおいてもう一度送信してください。", event)

    # message_id 記録
    processed_ids.append(message_id)
    processed_ids = processed_ids[-100:]
    with open(PROCESSED_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(processed_ids, f, ensure_ascii=False, indent=2)

# --------------------------------------------------
# テキスト応答
# --------------------------------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    text = event.message.text.strip()
    if text == "何が好き？":
        reply("チョコミントよりもあ・な・た", event)
    elif text.endswith("募"):
        reply("🆑", event)
    elif text.endswith("ちゃん！"):
        reply("はーい", event)
    elif text.endswith("ちんげのきたろう"):
        reply("受け取りました：ちんげのきたろう", event)
    elif text.endswith("ダディダディ"):
        reply(f"どすこいわっしょいピーポーピーポ―{text}～", event)
    elif text.endswith("途中経過"):
        name = text.replace("途中経過", "").strip()
        send_progress(name, event)

# --------------------------------------------------
# 忘れ回数チェック
# --------------------------------------------------
def send_progress(name: str, event):
    if not os.path.exists(MEMBERS_PATH) or not os.path.exists(DAILY_CSV_PATH):
        reply("データがありません。", event)
        return

    with open(MEMBERS_PATH, "r", encoding="utf-8") as f:
        id_to_name = json.load(f)
    names = list(id_to_name.values())
    if name not in names:
        reply("その名前は登録されていません。", event)
        return

    index = names.index(name)
    with open(DAILY_CSV_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    missed = sum(1 for row in rows if len(row) > index and row[index] == "1")
    reply(f"{name}は今月{missed}回忘れてます", event)

# --------------------------------------------------
# 共通リプライ関数（安全版）
# --------------------------------------------------
def reply(message: str, event):
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
    except Exception as e:
        print("❌ 通常リプライ失敗:", e)

def safe_reply(message: str, event):
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
    except LineBotApiError as e:
        print(f"❌ reply_token 使用失敗: {e}")
    except Exception as e:
        print(f"❌ その他のリプライエラー: {e}")

# --------------------------------------------------
# ヘルスチェック
# --------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"

# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
