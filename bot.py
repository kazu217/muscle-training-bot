# -*- coding: utf-8 -*-
"""LINE Bot main server (Render)
--------------------------------------------------
機能:
1. 画像/動画を受信すると大学サーバー(API)へ user_id と日付を POST
   （重複投稿なら duplicate_with も送る）
2. 固定フレーズ応答
3. 「<名前>途中経過」で今月の忘れ回数を返信
4. `/` に "LINE bot is alive" を返す
"""

import csv
import json
import os
import hashlib
import time
from datetime import datetime, timezone, timedelta

import requests
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import LineBotApiError
from linebot.models import (
    ImageMessage, VideoMessage, MessageEvent,
    TextMessage, TextSendMessage
)

# --------------------------------------------------
# パス & 定数
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
UNIV_TIMEOUT_SEC = 5   # 大学サーバーへの同期送信タイムアウト

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
# 共通ユーティリティ
# --------------------------------------------------
JST = timezone(timedelta(hours=9))


def now_jst():
    return datetime.now(JST)


def fetch_content_with_retry(message_id: str, retries: int = 3, delay: float = 0.3):
    """LINE サーバーからメディアを取得。400 Bad Request が出る場合があるのでリトライ"""
    for i in range(retries):
        try:
            return line_bot_api.get_message_content(message_id).content
        except LineBotApiError as e:
            if e.status_code == 400 and i < retries - 1:
                time.sleep(delay)
                continue
            raise


def safe_reply(message: str, event):
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
    except LineBotApiError as e:
        print(f"❌ reply_token 使用失敗: {e}")
    except Exception as e:
        print(f"❌ その他のリプライエラー: {e}")


def reply(message: str, event):
    """デバッグ・短文用"""
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
    except Exception as e:
        print("❌ 通常リプライ失敗:", e)


# --------------------------------------------------
# Webhook
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
# 画像 / 動画 メッセージ
# --------------------------------------------------
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    # ---------- グループ判定 ----------
    try:
        if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
            print("👥 対象外グループ or 個別トーク → 無視")
            return
    except AttributeError:  # user / room など group_id が存在しない
        print("👤 個別/ルーム → 無視")
        return
    # ----------------------------------

    message_id = event.message.id

    # ---------- 再送防止 ----------
    with open(PROCESSED_IDS_PATH, "r", encoding="utf-8") as f:
        processed_ids = json.load(f)
    if message_id in processed_ids:
        print(f"🔁 {message_id} は処理済み → スキップ")
        return
    processed_ids.append(message_id)
    with open(PROCESSED_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(processed_ids, f, ensure_ascii=False, indent=2)
    # ----------------------------------

    user_id = event.source.user_id
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
    print(f"📸 {today} {now.time()} に {user_id} がメディア送信")

    # ---------- メディア取得 ----------
    try:
        content = fetch_content_with_retry(message_id)
    except LineBotApiError as e:
        print(f"❌ コンテンツ取得失敗: {e}")
        # フラグ巻き戻し
        processed_ids.remove(message_id)
        with open(PROCESSED_IDS_PATH, "w", encoding="utf-8") as f:
            json.dump(processed_ids, f, ensure_ascii=False, indent=2)
        return

    if len(content) < 100:
        print("⚠️ メディアが小さすぎる → 無視")
        processed_ids.remove(message_id)
        with open(PROCESSED_IDS_PATH, "w", encoding="utf-8") as f:
            json.dump(processed_ids, f, ensure_ascii=False, indent=2)
        return
    # ----------------------------------

    content_hash = hashlib.sha256(content).hexdigest()

    # ---------- ローカルログ読み込み ----------
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
    # -------------------------------------------

    # ---------- 今日すでに投稿? ----------
    if any((entry == today or isinstance(entry, dict) and entry.get("date") == today) for entry in logs[name]):
        print(f"⚠️ {name} は今日すでに投稿済み")
        safe_reply("すでに今日の投稿は受け取っています！", event)
        return
    # ----------------------------------

    # ---------- 重複判定 ----------
    if content_hash in user_hashes:
        duplicated_date = user_hashes[content_hash]
        print(f"⚠️ 重複メディア ({duplicated_date})")
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
                },
                timeout=UNIV_TIMEOUT_SEC
            )
        except requests.exceptions.RequestException as e:
            print("❌ 重複通知失敗:", e)
        safe_reply(f"⚠️ 重複画像/動画。{duplicated_date} の投稿と一致", event)
        return
    # ----------------------------------

    # ---------- 新規メディア: ローカル更新 ----------
    user_hashes[content_hash] = today
    hash_log[user_id] = user_hashes
    with open(HASH_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(hash_log, f, ensure_ascii=False, indent=2)

    logs[name].append(now_iso)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    # ----------------------------------

    # ---------- 大学サーバー送信 (同期・タイムアウト5秒) ----------
    try:
        res = requests.post(
            UNIV_SERVER_ENDPOINT,
            json={"user_id": user_id, "date": today},
            timeout=UNIV_TIMEOUT_SEC
        )
        print("✅ 大学サーバー送信:", res.status_code)
        safe_reply("受け取りました！", event)
    except requests.exceptions.RequestException as e:
        print("❌ 大学サーバー送信失敗:", e)
        safe_reply("⚠️ 大学サーバーへ記録できませんでした。\n時間をおいて再送してください。", event)
    # ----------------------------------

    # ---------- processed_ids 整理 ----------
    processed_ids = processed_ids[-100:]
    with open(PROCESSED_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(processed_ids, f, ensure_ascii=False, indent=2)
    # --------------------------------------

# --------------------------------------------------
# テキスト応答
# --------------------------------------------------
@handler.add(MessageEvent, message=TextMessage))
def handle_text(event):
    # グループ判定
    try:
        if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
            return
    except AttributeError:
        return

    text = event.message.text.strip()
    if text == "何が好き？":
        reply("チョコミントよりもあ・な・た", event)
    elif text.endswith("募"):
        reply("㋕", event)
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
# ヘルスチェック
# --------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"

# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
