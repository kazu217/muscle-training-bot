import os
import requests
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, ImageMessage, VideoMessage, TextMessage, TextSendMessage
from datetime import datetime

load_dotenv()

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 大学サーバーの記録用APIエンドポイント
UNIV_SERVER_ENDPOINT = "https://e111-131-113-97-12.ngrok-free.app/record"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("❌ Webhook handling error:", e)
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    user_id = event.source.user_id
    today = datetime.now().strftime('%Y-%m-%d')
    print(f" {today} に {user_id} が画像/動画を送信")

    if event.source.type == "group":
        group_id = event.source.group_id
        print(f" グループID: {group_id}")
    else:
        print(" 個人チャットからの投稿です")

    # POST送信
    try:
        res = requests.post(UNIV_SERVER_ENDPOINT, json={
            "user_id": user_id,
            "date": today
        })
        print(" 大学サーバーに送信成功", res.status_code)
    except Exception as e:
        print("❌ 大学サーバーへの送信失敗", e)

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    text = event.message.text.strip()

    # 固定フレーズ：質問「何が好き？」にだけ返す
    if text == "何が好き？":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="チョコミントよりもあ・な・た")
        )
        return

    # 「○○ちゃん！」→「はーい」
    if text.endswith("ちゃん！"):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="はーい")
        )
        return

    # 「○○ダディダディ」→「どすこいわっしょいピーポーピーポ―○○ダディダディ～」
    if text.endswith("ダディダディ"):
        reply = f"どすこいわっしょいピーポーピーポ―{text}～"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return

    if text.endswith("途中経過"):
　　    name = text.replace("途中経過", "")
    	if not os.path.exists("members.json") or not os.path.exists("daily.csv"):
     	    line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="データがありません。")
            )
            return
    with open("members.json", "r", encoding="utf-8") as f:
        id_to_name = json.load(f)
    name_to_index = {v: i for i, v in enumerate(id_to_name.values())}
    if name not in name_to_index:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="その名前は登録されていません。")
        )
        return
    index = name_to_index[name]
    with open("daily.csv", "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    count = sum(1 for row in rows if len(row) > index and row[index] == "1")
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"{name}は今月{count}回忘れてます")
    )
    return


@app.route("/", methods=["GET"])
def index():
    return "LINE bot is alive"
