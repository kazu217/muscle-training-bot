import os
import requests
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage ,ImageMessage, VideoMessage
from datetime import datetime

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 大学サーバーの記録用APIエンドポイント
UNIV_SERVER_ENDPOINT = "https://e111-131-113-97-12.ngrok-free.app/record"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    user_id = event.source.user_id
    today = datetime.now().strftime('%Y-%m-%d')

    print(f"📸 {today} に {user_id} が画像/動画を送信")

    # ✅ グループID表示（LINEグループ投稿時のみ取得可能）
    if event.source.type == "group":
        group_id = event.source.group_id
        print(f"📢 グループID: {group_id}")
    else:
        print("👤 個人チャットからの投稿です")

    # 大学サーバーにPOST送信
    try:
        res = requests.post(UNIV_SERVER_ENDPOINT, json={
            "user_id": user_id,
            "date": today
        })
        print("✅ 大学サーバーに送信成功", res.status_code)
    except Exception as e:
        print("❌ 大学サーバーへの送信失敗", e)

    # LINE返信
    """line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"受け取りました: {text}")
    )"""

