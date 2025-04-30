# RenderのBotから大学サーバーに投稿記録を転送する構成
# Render側ではログ保存せず、大学サーバーにPOSTで記録だけ渡す

import os
import requests  # ← 大学サーバーにPOSTするため
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from datetime import datetime

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 大学サーバーの記録用APIエンドポイント（あなたのサーバーIPに書き換える）
UNIV_SERVER_ENDPOINT = "https://81e3-131-113-97-12.ngrok-free.app/record"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text
    today = datetime.now().strftime('%Y-%m-%d')
    print(f" {today} に {user_id} から: {text}")

    # 大学サーバーにPOST送信（ログ保存は大学側で行う）
    try:
        res = requests.post(UNIV_SERVER_ENDPOINT, json={
            "user_id": user_id,
            "date": today
        })
        print(" 大学サーバーに送信成功", res.status_code)
    except Exception as e:
        print(" 大学サーバーへの送信失敗", e)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"受け取りました: {text}")
    )
