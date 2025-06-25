# -*- coding: utf-8 -*-
"""LINE Bot main server (Render)
--------------------------------------------------
機能:
1. 画像/動画を受信すると大学サーバー(API)へ user_id と日付を POST
2. 固定フレーズ応答
3. 「<名前>途中経過」で今月の忘れ回数を返信
4. `/` に "LINE bot is alive" を返す
"""

import csv, json, os, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

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
# ディレクトリ固定
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent   # = ~/musclebot
os.chdir(BASE_DIR)                           # ★ これで相対パスは常に ~/musclebot


# ★★★ ここからデバッグ用 ★★★
import os, sys
print("★ CWD:", os.getcwd(), file=sys.stderr)
print("★ bot.py:", __file__, file=sys.stderr)
print("★ LOG_PATH:", (Path('log.json')).resolve(), file=sys.stderr)
# ★★★★★★★★★★★★★★★★★★★★


# --------------------------------------------------
# ファイルパス
# --------------------------------------------------
LOG_PATH        = Path("log.json")
MEMBERS_PATH    = Path("members.json")
DAILY_CSV_PATH  = Path("daily.csv")

# --------------------------------------------------
# 環境変数
# --------------------------------------------------
load_dotenv()
LINE_TOKEN  = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_GROUP_ID = "C1d9ed412f2141da57e47bd28cec532a4"
UNIV_SERVER_ENDPOINT = "https://e111-131-113-97-12.ngrok-free.app/record"

# --------------------------------------------------
# 初期化
# --------------------------------------------------
app = Flask(__name__)
line_bot_api = LineBotApi(LINE_TOKEN)
handler      = WebhookHandler(LINE_SECRET)

if not LOG_PATH.exists():
    LOG_PATH.write_text("{}", encoding="utf-8")

JST = timezone(timedelta(hours=9))

# --------------------------------------------------
# Webhook
# --------------------------------------------------
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

# --------------------------------------------------
# メディア処理
# --------------------------------------------------
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    # グループ判定
    if not (event.source.type == "group" and event.source.group_id == LINE_GROUP_ID):
        return
    if event.message.content_provider.type != "line":
        return

    user_id = event.source.user_id
    now     = datetime.now(JST)
    today   = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
    print(f"📸 {today} {now.time()} by {user_id}")

    # 名前取得
    with open(MEMBERS_PATH, "r", encoding="utf-8") as f:
        id_to_name = json.load(f)
    name = id_to_name.get(user_id, user_id)

    # log.json 読み込み
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)
    if name not in logs:
        logs[name] = []

    # 今日すでに投稿済み？
    if any(entry.startswith(today) for entry in logs[name]):
        safe_reply("すでに今日の投稿は受け取っています！", event)
        return

    # 記録
    logs[name].append(now_iso)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    print("✅ log.json に追記完了")

    # 大学サーバーへ送信（失敗は無視）
    try:
        requests.post(UNIV_SERVER_ENDPOINT,
                      json={"user_id": user_id, "date": today},
                      timeout=5)
    except Exception as e:
        print("❌ 大学サーバー送信失敗:", e)

    safe_reply("受け取りました！", event)

# --------------------------------------------------
# テキスト応答
# --------------------------------------------------
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

# --------------------------------------------------
# 途中経過
# --------------------------------------------------
def send_progress(name: str, event):
    if not (MEMBERS_PATH.exists() and DAILY_CSV_PATH.exists()):
        reply("データがありません。", event); return
    with open(MEMBERS_PATH, "r", encoding="utf-8") as f:
        names = list(json.load(f).values())
    if name not in names:
        reply("その名前は登録されていません。", event); return
    idx = names.index(name)
    with open(DAILY_CSV_PATH, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    missed = sum(1 for r in rows if len(r) > idx and r[idx] == "1")
    reply(f"{name}は今月{missed}回忘れてます", event)

# --------------------------------------------------
# 返信ヘルパ
# --------------------------------------------------
def reply(msg: str, event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

def safe_reply(msg: str, event):
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
    except LineBotApiError:
        pass

# --------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
