# -*- coding: utf-8 -*-
"""LINE Bot main server (Render)
sss--------------------------------------------------
機能:
1. 画像/動画を受信すると大学サーバー(API)へ user_id と日付を POST（ただし重複投稿は除外）
2. 固定フレーズ応答 ("何が好き?", "○○ちゃん!", "○○ダディダディ")
3. 「<名前>途中経過」と送ると daily.csv から今月の忘れ回数を返信
4. ルート `/` でヘルスチェック用 "LINE bot is alive" を返す

依存:
- python-dotenv
- line-bot-sdk>=2  (v2 のまま使用)
- Flask

環境変数 (.env or Render 変数):
- LINE_CHANNEL_ACCESS_TOKEN
- LINE_CHANNEL_SECRET

大学サーバー側に record.py が動いている前提で、UNIV_SERVER_ENDPOINT を
ngrok URL + "/record" にしておくこと。
"""

import csv
import json
import os
import hashlib
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    ImageMessage,
    MessageEvent,
    TextMessage,
    TextSendMessage,
    VideoMessage,
)

load_dotenv()
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
UNIV_SERVER_ENDPOINT = "https://e111-131-113-97-12.ngrok-free.app/record"

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

HASH_LOG_PATH = "hash_log.json"
if not os.path.exists(HASH_LOG_PATH):
    with open(HASH_LOG_PATH, "w") as f:
        json.dump({}, f)

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

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    user_id = event.source.user_id
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📸 {today} に {user_id} が画像/動画を送信")

    message_id = event.message.id
    content = line_bot_api.get_message_content(message_id).content
    content_hash = hashlib.sha256(content).hexdigest()

    with open(HASH_LOG_PATH, "r") as f:
        hash_log = json.load(f)

    if content_hash in hash_log.get(user_id, []):
        reply("⚠　！", event)
        print("⚠️ 重複画像/動画。記録せず！")
        return

    hash_log.setdefault(user_id, []).append(content_hash)
    with open(HASH_LOG_PATH, "w") as f:
        json.dump(hash_log, f, ensure_ascii=False, indent=2)

    if event.source.type == "group":
        print(f"📢 グループID: {event.source.group_id}")

    try:
        res = requests.post(UNIV_SERVER_ENDPOINT, json={"user_id": user_id, "date": today})
        print("✅ 大学サーバーに送信成功", res.status_code)
    except Exception as e:
        print("❌ 大学サーバーへの送信失敗", e)
    reply("⚠️ エラー：記録に失敗しました。時間をおいてもう一度送信してください。", event)

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    text = event.message.text.strip()

    if text == "何が好き？":
        reply("チョコミントよりもあ・な・た", event)
        return

    if text.endswith("募"):
        reply("🉑", event)
        return

    if text.endswith("ちゃん！"):
        reply("はーい", event)
        return

    if text.endswith("ちんげのきたろう"):
        reply("受け取りました：ちんげのきたろう", event)
        return

    if text.endswith("ダディダディ"):
        reply(f"どすこいわっしょいピーポーピーポ―{text}～", event)
        return

    if text.endswith("途中経過"):
        name = text.replace("途中経過", "").strip()
        send_progress(name, event)
        return

def send_progress(name: str, event):
    if not os.path.exists("members.json") or not os.path.exists("daily.csv"):
        reply("データがありません。", event)
        return

    with open("members.json", "r", encoding="utf-8") as f:
        id_to_name = json.load(f)

    names = list(id_to_name.values())
    if name not in names:
        reply("その名前は登録されていません。", event)
        return
    index = names.index(name)

    with open("daily.csv", "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    missed = sum(1 for row in rows if len(row) > index and row[index] == "1")

    reply(f"{name}は今月{missed}回忘れてます", event)

def reply(message: str, event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))

@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
