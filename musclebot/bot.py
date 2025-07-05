#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE Bot  (Render 実行用)

機能
────
1. 画像/動画を受信すると大学サーバー (/record) へ user_id と日付を POST
   ︙   current_ngrok_url.txt に書かれた URL を毎回読むので、
        watch_ngrok.sh で URL が変わっても自動追従
2. 固定フレーズ応答
3. 「<名前>途中経過」で今月の忘れ回数を返信
4. / で "LINE bot is alive" を返す
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

# ───────────────────────────────────────────────
# ディレクトリ固定  (Render の CWD は /opt/render/project/src)
# ───────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent          # …/musclebot
os.chdir(BASE_DIR)                                  # ここを基準にファイルを扱う

# ───────────────────────────────────────────────
# ファイルパス定義
# ───────────────────────────────────────────────
LOG_PATH            = BASE_DIR / "log.json"
MEMBERS_PATH        = BASE_DIR / "members.json"
DAILY_CSV_PATH      = BASE_DIR / "daily.csv"
NGROK_URL_FILE      = BASE_DIR / "current_ngrok_url.txt"   # watch_ngrok.sh が更新
DEFAULT_ENDPOINT    = ""                                   # 読めなければ空 = 送信しない

# ───────────────────────────────────────────────
# .env 読み込み
# ───────────────────────────────────────────────
load_dotenv()
LINE_TOKEN      = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET     = os.getenv("LINE_CHANNEL_SECRET")
LINE_GROUP_ID   = "C1d9ed412f2141da57e47bd28cec532a4"

# ───────────────────────────────────────────────
# Flask & LINE 初期化
# ───────────────────────────────────────────────
app     = Flask(__name__)
bot     = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)
JST     = timezone(timedelta(hours=9))

# log.json 初期化
if not LOG_PATH.exists():
    LOG_PATH.write_text("{}", encoding="utf-8")

# ───────────────────────────────────────────────
# 大学サーバー URL を読むユーティリティ
# ───────────────────────────────────────────────
def get_univ_endpoint() -> str:
    """current_ngrok_url.txt → https://xxxx.ngrok-free.app/record"""
    try:
        url = NGROK_URL_FILE.read_text(encoding="utf-8").strip()
        if url.startswith("http"):
            return f"{url}/record"
    except Exception as e:
        print("⚠️ current_ngrok_url.txt 読み取り失敗:", e)
    return DEFAULT_ENDPOINT

# ───────────────────────────────────────────────
# ルーティング
# ───────────────────────────────────────────────
@app.before_request
def debug_ping():
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
# メディア受信
# ───────────────────────────────────────────────
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    # 限定グループのみ
    if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
        return
    if event.message.content_provider.type != "line":
        return

    uid    = event.source.user_id
    now    = datetime.now(JST)
    today  = now.strftime("%Y-%m-%d")
    nowiso = now.isoformat()
    print(f"📸 uid='{uid}' today='{today}' {now.time()}")

    # 名前解決
    name = uid
    if MEMBERS_PATH.exists():
        try:
            id2name = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
            name = id2name.get(uid, uid)
        except Exception as e:
            print("⚠️ members.json 読み込み失敗:", e)

    # log.json
    logs = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    logs.setdefault(name, [])
    if any(str(x).startswith(today) for x in logs[name]):
        safe_reply("すでに今日の投稿は受け取っています！", event)
        return

    logs[name].append(nowiso)
    LOG_PATH.write_text(json.dumps(logs, ensure_ascii=False, indent=2))
    print("✅ log.json 追記 OK")

    # 大学サーバーへ
    endpoint = get_univ_endpoint()
    if endpoint:
        try:
            res = requests.post(endpoint,
                                json={"user_id": uid, "date": today},
                                timeout=5)
            print("📡 record.py status:", res.status_code, res.text[:120])
        except requests.exceptions.RequestException as e:
            print("❌ 大学サーバー送信失敗:", e)
    else:
        print("⚠️ endpoint 未設定 → 送信スキップ")

    safe_reply("受け取りました！", event)

# ───────────────────────────────────────────────
# テキスト応答
# ───────────────────────────────────────────────
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
        name = txt.replace("途中経過", "").strip()
        send_progress(name, event)

# ───────────────────────────────────────────────
def send_progress(name: str, event):
    if not (MEMBERS_PATH.exists() and DAILY_CSV_PATH.exists()):
        reply("データがありません。", event)
        return
    names = list(json.loads(MEMBERS_PATH.read_text(encoding="utf-8")).values())
    if name not in names:
        reply("その名前は登録されていません。", event)
        return
    idx  = names.index(name)
    rows = list(csv.reader(open(DAILY_CSV_PATH, newline='', encoding="utf-8")))
    missed = sum(1 for r in rows if len(r) > idx and r[idx] == "1")
    reply(f"{name}は今月{missed}回忘れてます", event)

# ───────────────────────────────────────────────
def reply(msg: str, event):
    bot.reply_message(event.reply_token, TextSendMessage(text=msg))

def safe_reply(msg: str, event):
    try:
        bot.reply_message(event.reply_token, TextSendMessage(text=msg))
    except LineBotApiError:
        pass

# ───────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"

# Render 用：ファイル一覧
@app.route("/files", methods=["GET"])
def list_files():
    return {"files": os.listdir(BASE_DIR)}

# ───────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
