# -*- coding: utf-8 -*-
"""
LINE Bot (Render)
────────────────────────────────────────
- 画像/動画を受信 → 大学サーバー /record へ POST
- 固定フレーズ応答
- "<名前>途中経過" で忘れ回数返答
- /env で NGROK_RECORD_URL を確認
- /files でデプロイ環境の musclebot ディレクトリ内容を確認
"""

from __future__ import annotations
import os
import json
import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import LineBotApiError
from linebot.models import (
    MessageEvent, ImageMessage, VideoMessage,
    TextMessage, TextSendMessage
)

# ───────────────────────────────────────────────
# パス固定：以降の相対パスは musclebot ディレクトリ内に固定
# ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent  # 例: /opt/render/project/src/musclebot
os.chdir(BASE_DIR)

LOG_PATH       = Path("log.json")
MEMBERS_PATH   = Path("members.json")
DAILY_CSV_PATH = Path("daily.csv")

# ───────────────────────────────────────────────
# 環境変数
# ───────────────────────────────────────────────
load_dotenv()
LINE_TOKEN    = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET   = os.getenv("LINE_CHANNEL_SECRET")
LINE_GROUP_ID = "C1d9ed412f2141da57e47bd28cec532a4"  # ←必要に応じて更新

# ngrok URL は Render の環境変数から取得（watch_ngrok.sh で更新している前提）
_raw = os.getenv("NGROK_RECORD_URL")
print(f"NGROK_RECORD_URL(raw)={repr(_raw)}")  # 起動ログで確認用
NGROK_RECORD_URL = (_raw or "").strip().rstrip("/")
ENDPOINT = f"{NGROK_RECORD_URL}/record" if NGROK_RECORD_URL else None
if ENDPOINT:
    print(f"✅ ENDPOINT set to {ENDPOINT}")
else:
    print("⚠️ NGROK_RECORD_URL 未設定。大学サーバー通知はスキップします。")

# ───────────────────────────────────────────────
# Flask / LINE 初期化
# ───────────────────────────────────────────────
app     = Flask(__name__)
bot     = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)
JST     = timezone(timedelta(hours=9))

# log.json なければ空の辞書で作る
if not LOG_PATH.exists():
    LOG_PATH.write_text("{}", encoding="utf-8")

# ───────────────────────────────────────────────
# Webhook
# ───────────────────────────────────────────────
@app.before_request
def _debug_before():
    if request.path == "/callback":
        print("🔔 /callback hit")

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("❌ Webhook handling error:", e)
        abort(400)
    return "OK"

# ───────────────────────────────────────────────
# 画像/動画
# ───────────────────────────────────────────────
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    # 指定グループのみ
    if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
        return
    # LINE 内メディアのみ（外部URLは無視）
    if event.message.content_provider.type != "line":
        return

    uid     = event.source.user_id
    now     = datetime.now(JST)
    today   = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
    print(f"📸 uid='{uid}' today='{today}' {now.time()}")

    # 名前解決
    name = uid
    if MEMBERS_PATH.exists():
        try:
            id_to_name = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
            name = id_to_name.get(uid, uid)
        except Exception as e:
            print("⚠️ members.json 読み込み失敗:", e)

    # log.json 更新（その人は1日1回だけ）
    try:
        logs = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        logs = {}
    logs.setdefault(name, [])

    # その人の今日の記録が既にある？
    if any(str(entry).startswith(today) for entry in logs[name]):
        safe_reply("すでに今日の投稿は受け取っています！", event)
        return

    logs[name].append(now_iso)
    LOG_PATH.write_text(json.dumps(logs, ensure_ascii=False, indent=2))
    print("✅ log.json 追記 OK")

    # 大学サーバーへ通知
    if ENDPOINT:
        try:
            res = requests.post(ENDPOINT, json={"user_id": uid, "date": today}, timeout=5)
            print("📡 record.py status:", res.status_code, res.text[:200])
        except requests.exceptions.RequestException as e:
            print("❌ 大学サーバー送信失敗:", e)
    else:
        print("⚠️ endpoint 未設定 → 送信スキップ")

    safe_reply("受け取りました！", event)

# ───────────────────────────────────────────────
# テキスト
# ───────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    txt = event.message.text.strip()

    if txt == "何が好き？":
        reply("チョコミントよりもあ・な・た", event)
        return
    if txt.endswith("募"):
        reply("🉑", event)
        return
    if txt.endswith("ちゃん！"):
        reply("はーい", event)
        return
    if txt.endswith("ちんげのきたろう"):
        reply("受け取りました：ちんげのきたろう", event)
        return
    if txt.endswith("ダディダディ"):
        reply(f"どすこいわっしょいピーポーピーポ―{txt}～", event)
        return

    if txt.endswith("途中経過"):
        name = txt.replace("途中経過", "").strip()
        send_progress(name, event)
        return

# ───────────────────────────────────────────────
# 途中経過（daily.csv をカウント）
# ───────────────────────────────────────────────
def send_progress(name: str, event):
    if not (MEMBERS_PATH.exists() and DAILY_CSV_PATH.exists()):
        reply("データがありません。", event)
        return

    try:
        id_to_name = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
        names = list(id_to_name.values())
    except Exception:
        reply("メンバー情報の読み込みに失敗しました。", event)
        return

    if name not in names:
        reply("その名前は登録されていません。", event)
        return
    idx = names.index(name)

    try:
        with open(DAILY_CSV_PATH, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        missed = sum(1 for r in rows if len(r) > idx and r[idx] == "1")
        reply(f"{name}は今月{missed}回忘れてます", event)
    except Exception:
        reply("記録ファイルの読み込みに失敗しました。", event)

# ───────────────────────────────────────────────
# 返信ヘルパ
# ───────────────────────────────────────────────
def reply(msg: str, event):
    bot.reply_message(event.reply_token, TextSendMessage(text=msg))

def safe_reply(msg: str, event):
    try:
        bot.reply_message(event.reply_token, TextSendMessage(text=msg))
    except LineBotApiError:
        pass

# ───────────────────────────────────────────────
# ヘルスチェック / デバッグ
# ───────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"

@app.route("/files", methods=["GET"])
def list_files():
    # Render 上の musclebot ディレクトリの一覧
    return {"files": os.listdir(BASE_DIR)}

@app.route("/env", methods=["GET"])
def show_env():
    # 大学サーバーの ngrok URL が見えるか確認用
    return {"NGROK_RECORD_URL": os.getenv("NGROK_RECORD_URL", "")}

# ───────────────────────────────────────────────
if __name__ == "__main__":
    # ローカル実行用
    app.run(host="0.0.0.0", port=5000)
