import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from datetime import datetime

# ✅ 環境変数チェック（Noneのままだとエラーで止まるため）
token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
secret = os.getenv("LINE_CHANNEL_SECRET")

if not token or not secret:
    print("❌ 環境変数が設定されていません。")
    print("LINE_CHANNEL_ACCESS_TOKEN:", token)
    print("LINE_CHANNEL_SECRET:", secret)
    exit(1)

print("✅ 環境変数の読み込み成功")

# ✅ Flaskインスタンス作成
app = Flask(__name__)
line_bot_api = LineBotApi(token)
handler = WebhookHandler(secret)

# ✅ LINEのWebhookを受け取るルート
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("❌ handler.handleエラー:", e)
        abort(400)

    return 'OK'

# ✅ メッセージイベント処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text
    today = datetime.now().strftime('%Y-%m-%d')

    print(f"✅ {today} に {user_id} から: {text}")

    # 投稿ログを保存
    log_file = "log.json"
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = {}

    if today not in logs:
        logs[today] = []
    if user_id not in logs[today]:
        logs[today].append(user_id)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

    # 応答を返す
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"受け取りました: {text}")
    )

# ✅ Flask起動部分
print("✅ Flask 起動準備完了")

if __name__ == "__main__":
    print("🚀 Flask を起動します")
    app.run(host="0.0.0.0", port=5000)


