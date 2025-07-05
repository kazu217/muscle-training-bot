import os, json, csv, time, hashlib
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
# パス固定
# ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent          # /opt/render/project/src/musclebot
ROOT_DIR = BASE_DIR                                 # ここにファイルを置く
os.chdir(ROOT_DIR)

# ───────────────────────────────────────────────
# 主要ファイル
# ───────────────────────────────────────────────
LOG_PATH       = ROOT_DIR / "log.json"
MEMBERS_PATH   = ROOT_DIR / "members.json"
DAILY_CSV_PATH = ROOT_DIR / "daily.csv"

# ───────────────────────────────────────────────
# .env
# ───────────────────────────────────────────────
load_dotenv()
LINE_TOKEN      = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET     = os.getenv("LINE_CHANNEL_SECRET")
LINE_GROUP_ID   = "C1d9ed412f2141da57e47bd28cec532a4"
UNIV_SERVER_ENDPOINT = "https://e111-131-113-97-12.ngrok-free.app/record"

# ───────────────────────────────────────────────
# Flask + LINE 初期化
# ───────────────────────────────────────────────
app     = Flask(__name__)
bot     = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)
JST     = timezone(timedelta(hours=9))

# log.json を準備
if not LOG_PATH.exists():
    LOG_PATH.write_text("{}", encoding="utf-8")

# ───────────────────────────────────────────────
# ★ Webhook 呼び出し確認
# ───────────────────────────────────────────────
@app.before_request
def debug_before_request():
    if request.path == "/callback":
        print("🔔 /callback hit!")

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
    # 指定グループのみ
    if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
        return
    if event.message.content_provider.type != "line":
        return

    user_id = event.source.user_id
    now     = datetime.now(JST)
    today   = now.strftime("%Y-%m-%d")
    now_iso = now.isoformat()
    print(f"📸 {user_id=} {today=} {now.time()}")

    # 名前解決
    name = user_id
    if MEMBERS_PATH.exists():
        try:
            id_to_name = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
            name = id_to_name.get(user_id, user_id)
        except Exception as e:
            print("⚠️ members.json 読み込み失敗:", e)

    # log.json 読み込み
    logs = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    logs.setdefault(name, [])

    # 既に本日記録済み？
    if any(str(entry).startswith(today) for entry in logs[name]):
        safe_reply("すでに今日の投稿は受け取っています！", event)
        return

    # 追記
    logs[name].append(now_iso)
    LOG_PATH.write_text(json.dumps(logs, ensure_ascii=False, indent=2))
    print("✅ log.json 追記 OK")

    # 大学サーバーへ
    try:
        res = requests.post(
            UNIV_SERVER_ENDPOINT,
            json={"user_id": user_id, "date": today},
            timeout=5
        )
        print("📡 record.py status:", res.status_code, res.text[:120])
    except requests.exceptions.RequestException as e:
        print("❌ 大学サーバー送信失敗:", e)

    safe_reply("受け取りました！", event)

# ───────────────────────────────────────────────
# テキスト
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
        reply("データがありません。", event); return
    names = list(json.loads(MEMBERS_PATH.read_text(encoding="utf-8")).values())
    if name not in names:
        reply("その名前は登録されていません。", event); return
    idx = names.index(name)
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

# Render 用：ファイル一覧確認
@app.route("/files", methods=["GET"])
def list_files():
    return {"files": os.listdir(ROOT_DIR)}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
