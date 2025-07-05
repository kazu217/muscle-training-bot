# -*- coding: utf-8 -*-
"""LINE Bot (Render)

画像/動画を受け取ったら大学サーバーへ
    {"user_id": "...", "date": "YYYY-MM-DD"}
を POST するだけ。ログ保存はしない。
"""

import os, json
from pathlib import Path
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

# ───────────────────────────────────────────────
# ★ ディレクトリ固定（必ず bot.py と同じ階層にする）
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)          # これ以降の相対パスは BASE_DIR 基準
# ───────────────────────────────────────────────

# ───── 環境変数 ─────
load_dotenv()
LINE_TOKEN   = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET  = os.getenv("LINE_CHANNEL_SECRET")

# 投稿を受け付けるグループ ID（必須であれば設定）
LINE_GROUP_ID = "C1d9ed412f2141da57e47bd28cec532a4"

# 大学サーバー（ngrok 等）のエンドポイント
UNIV_SERVER_ENDPOINT = "https://e111-131-113-97-12.ngrok-free.app/record"

# ───── Flask + LINE 初期化 ─────
app = Flask(__name__)
bot = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

JST = timezone(timedelta(hours=9))

# ───────────────────────────────────────────────
# Webhook
# ───────────────────────────────────────────────
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
# 画像 / 動画
# ───────────────────────────────────────────────
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    # グループ限定にしたい場合
    if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
        return
    if event.message.content_provider.type != "line":
        return

    user_id = event.source.user_id
    today   = datetime.now(JST).strftime("%Y-%m-%d")
    print(f"📸 受信: {user_id=} {today=}")

    # ── 大学サーバーへ送信 ──
    try:
        res = requests.post(
            UNIV_SERVER_ENDPOINT,
            json={"user_id": user_id, "date": today},
            timeout=5
        )
        print("📡 record.py status:", res.status_code, res.text[:120])
    except requests.exceptions.RequestException as e:
        print("❌ 大学サーバー送信失敗:", e)

    # ユーザーへ返答
    safe_reply("受け取りました！", event)

# ───────────────────────────────────────────────
# テキスト応答（必要最低限）
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
    # 「途中経過」系は大学サーバー側 daily_check の結果を読む想定なので
    # 必要ならここに実装してください

# ───────────────────────────────────────────────
# ヘルパ
# ───────────────────────────────────────────────
def reply(msg: str, event):
    bot.reply_message(event.reply_token, TextSendMessage(text=msg))

def safe_reply(msg: str, event):
    try:
        bot.reply_message(event.reply_token, TextSendMessage(text=msg))
    except LineBotApiError:
        pass

# デバッグ用：Render 上のファイル一覧を確認できる
@app.route("/files", methods=["GET"])
def list_files():
    return {"files": os.listdir(BASE_DIR)}

@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

