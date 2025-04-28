from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv("dqTKCzxGnIr9brULUos/Yf4W9qtopmJh1OPQtqBLbzbktMapBtCJrx1qIDIFp/oKn9aWPEasTDnBxy6Jh9BOAw1t+40C1+2HGLYY2I2HsRTn5S4rBq+2UCAFTnz8wRF9ftrjcduyxoFCk1lckEEGigdB04t89/1O/w1cDnyilFU="))
handler = WebhookHandler(os.getenv("3c0793ea2cde4ad264e2b63d568343f6"))

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
    text = event.message.text
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"受け取りました: {text}")
    )

if __name__ == "__main__":
    app.run()
