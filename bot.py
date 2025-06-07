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
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    ImageMessage, VideoMessage, MessageEvent,
    TextMessage, TextSendMessage
)

# --------------------------------------------------
# 環境変数・定数
# --------------------------------------------------
load_dotenv()
LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
UNIV_SERVER_ENDPOINT = "https://e111-131-113-97-12.ngrok-free.app/record"
HASH_LOG_PATH = "hash_log.json"
LOG_PATH = "log.json"
LINE_GROUP_ID = "C1d9ed412f2141da57e47bd28cec532a4"

# --------------------------------------------------
# 初期化
# --------------------------------------------------
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

if not os.path.exists(HASH_LOG_PATH):
    with open(HASH_LOG_PATH, "w") as f:
        json.dump({}, f)
if not os.path.exists(LOG_PATH):
    with open(LOG_PATH, "w") as f:
        json.dump({}, f)

# --------------------------------------------------
# Webhook エンドポイント
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
# 画像・動画メッセージ受信
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
    with open(PROCESSED_IDS_PATH, "r") as f:
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

    # ハッシュログ読み込み
    with open(HASH_LOG_PATH, "r") as f:
        hash_log = json.load(f)
    user_hashes = hash_log.get(user_id, {})

    # 名前取得
    with open("members.json", "r", encoding="utf-8") as f:
        id_to_name = json.load(f)
    name = id_to_name.get(user_id, user_id)

    # log.json 読み込み
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = {}

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

    # 重複判定
    if content_hash in user_hashes:
        duplicated_date = user_hashes[content_hash]
        print(f"⚠️ 重複画像/動画。{duplicated_date} の投稿と一致")
        logs[name].append(f"重複: {duplicated_date}")
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

        try:
            requests.post(
                UNIV_SERVER_ENDPOINT,
                json={
                    "user_id": user_id,
                    "date": today,
                    "duplicate": True,
                    "duplicate_with": duplicated_date
                }
            )
        except Exception as e:
            print("❌ 重複通知失敗", e)

        safe_reply(f"⚠️ 重複画像/動画。{duplicated_date} の投稿と一致", event)
        return

    # 正常記録処理
    user_hashes[content_hash] = today
    hash_log[user_id] = user_hashes
    with open(HASH_LOG_PATH, "w") as f:
        json.dump(hash_log, f, ensure_ascii=False, indent=2)

    logs[name].append(now_iso)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

    try:
        res = requests.post(UNIV_SERVER_ENDPOINT, json={"user_id": user_id, "date": today})
        print("✅ 大学サーバーに送信成功", res.status_code)
        safe_reply("受け取りました！", event)
    except Exception as e:
        print("❌ 大学サーバーへの送信失敗", e)
        safe_reply("⚠️ エラー：記録に失敗しました。時間をおいてもう一度送信してください。", event)

    # イベントIDを記録（上限100件に制限して管理）
    processed_ids.append(message_id)
    processed_ids = processed_ids[-100:]
    with open(PROCESSED_IDS_PATH, "w") as f:
        json.dump(processed_ids, f)
# --------------------------------------------------
# テキストメッセージ応答
# --------------------------------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    text = event.message.text.strip()

    if text == "何が好き？":
        reply("チョコミントよりもあ・な・た", event)
        return
    if text.endswith("募"):
        reply("🆑", event)
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

# --------------------------------------------------
# 途中経過チェック
# --------------------------------------------------
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

# --------------------------------------------------
# 共通返信関数
# --------------------------------------------------
def reply(message: str, event):
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
    except Exception as e:
        print("❌ リプライ失敗:", e)

# --------------------------------------------------
# ヘルスチェックルート
# --------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"

# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
