"""from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage
import os, json
from datetime import datetime

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

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
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 記録用ファイル
    record_file = "log.json"
    if os.path.exists(record_file):
        with open(record_file, 'r') as f:
            logs = json.load(f)
    else:
        logs = {}

    if today not in logs:
        logs[today] = []
    if user_id not in logs[today]:
        logs[today].append(user_id)

    with open(record_file, 'w') as f:
        json.dump(logs, f)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)"""

from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "Flask is working!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

