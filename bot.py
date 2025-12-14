# -*- coding: utf-8 -*-
"""
LINE Bot (Render)
────────────────────────────────────────
- 画像/動画を受信 → 大学サーバー /record へ POST
- 固定フレーズ応答
- "<名前>途中経過" で忘れ回数返答
"""

from __future__ import annotations
import os, json, csv
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

# ────────────────── パス固定
BASE_DIR = Path(__file__).resolve().parent  # /opt/render/project/src/musclebot
os.chdir(BASE_DIR)                          # 以降の相対パスは musclebot 内

LOG_PATH       = Path("log.json")
MEMBERS_PATH   = Path("members.json")
DAILY_CSV_PATH = Path("daily.csv")

# ────────────────── .env / Render env
load_dotenv()
LINE_TOKEN      = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET     = os.getenv("LINE_CHANNEL_SECRET")
LINE_GROUP_ID   = "C1d9ed412f2141da57e47bd28cec532a4"

# ngrok URL は Render の環境変数から取得
NGROK_RECORD_URL = (os.getenv("NGROK_RECORD_URL") or "").rstrip("/")
if NGROK_RECORD_URL:
    ENDPOINT = f"{NGROK_RECORD_URL}/record"
else:
    print("⚠️ NGROK_RECORD_URL 未設定。大学サーバー通知はスキップします。")
    ENDPOINT = None

# ────────────────── Flask / LINE 初期化
app     = Flask(__name__)
bot     = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)
JST     = timezone(timedelta(hours=9))

if not LOG_PATH.exists():
    LOG_PATH.write_text("{}", encoding="utf-8")

# ────────────────── Webhook
@app.before_request
def _debug():
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

# ────────────────── 画像/動画
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
        return
#    if event.message.content_provider.type != "line":
#        return

    uid   = event.source.user_id
    now   = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
    print(f"📸 uid='{uid}' today='{today}' {now.time()}")

    # 名前解決
    name = uid
    if MEMBERS_PATH.exists():
        try:
            name = json.loads(MEMBERS_PATH.read_text()).get(uid, uid)
        except Exception as e:
            print("⚠️ members.json 読込失敗:", e)

    # log.json 更新
    logs = json.loads(LOG_PATH.read_text())
    logs.setdefault(name, [])
    if any(str(e).startswith(today) for e in logs[name]):
        safe_reply("すでに今日の投稿は受け取っています！", event)
        return
    logs[name].append(now_iso)
    LOG_PATH.write_text(json.dumps(logs, ensure_ascii=False, indent=2))
    print("✅ log.json 追記 OK")

    # 大学サーバーへ
    if ENDPOINT:
        try:
            res = requests.post(
                ENDPOINT, json={"user_id": uid, "date": today}, timeout=5
            )
            print("📡 record.py status:", res.status_code, res.text[:120])
        except requests.exceptions.RequestException as e:
            print("❌ 大学サーバー送信失敗:", e)
    else:
        print("⚠️ endpoint 未設定 → 送信スキップ")

    safe_reply("受け取りました！", event)

# ────────────────── テキスト
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    txt = event.message.text.strip()
    if txt == "何が好き？":
        reply("チョコミントよりもあ・な・た", event)
    elif txt.endswith("募"):
        reply("🆑", event)
    elif txt.endswith("ちゃん！"):
        reply("はーい", event)
    elif txt.endswith("ちんげのきたろう"):
        reply("受け取りました：ちんげのきたろう", event)
    elif txt.endswith("ダディダディ"):
        reply(f"どすこいわっしょいピーポーピーポ―{txt}～", event)
    elif txt.endswith("途中経過"):
        send_progress(txt.replace("途中経過", "").strip(), event)

# ────────────────── 途中経過
def send_progress(name: str, event):
    if not (MEMBERS_PATH.exists() and DAILY_CSV_PATH.exists()):
        reply("データがありません。", event); return
    names = list(json.loads(MEMBERS_PATH.read_text()).values())
    if name not in names:
        reply("その名前は登録されていません。", event); return
    idx = names.index(name)
    rows = csv.reader(open(DAILY_CSV_PATH, encoding="utf-8"))
    missed = sum(1 for r in rows if len(r) > idx and r[idx] == "1")
    reply(f"{name}は今月{missed}回忘れてます", event)

# ────────────────── ヘルパ
def reply(msg: str, event):       bot.reply_message(event.reply_token, TextSendMessage(text=msg))
def safe_reply(msg: str, event):
    try: bot.reply_message(event.reply_token, TextSendMessage(text=msg))
    except LineBotApiError: pass

@app.route("/", methods=["GET"])
def index(): return "LINE bot is alive"

# Render でファイル確認用
@app.route("/files", methods=["GET"])
def list_files(): return {"files": os.listdir(BASE_DIR)}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
