# ~/musclebot/bot.py
# -*- coding: utf-8 -*-
"""
LINE Bot main server
─────────────────────────────────────────────
1. 画像/動画を受信 → 大学サーバー(record.py)へ POST
2. 各種定型レスポンス / 忘れ回数集計
3. /  → ヘルスチェック
4. /files  → Render デバッグ用ファイル一覧
"""

import json, csv, os, sys, requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import LineBotApiError
from linebot.models import (
    MessageEvent, ImageMessage, VideoMessage,
    TextMessage, TextSendMessage,
)

# ──────────────────────────────────────────────
# ① 物理パスを固定（どこで実行しても ~/musclebot）
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent          # ~/musclebot
os.chdir(BASE_DIR)                                  # 以降の相対パスはここ基準

# 主ファイル
LOG_PATH        = BASE_DIR / "log.json"
MEMBERS_PATH    = BASE_DIR / "members.json"
DAILY_CSV_PATH  = BASE_DIR / "daily.csv"
NGROK_FILE      = BASE_DIR / "current_ngrok_url.txt"  # ← watch_ngrok.sh が更新

# log.json が無ければ空 dict で作成
if not LOG_PATH.exists():
    LOG_PATH.write_text("{}", encoding="utf-8")

# ──────────────────────────────────────────────
# ② .env 読み込み
# ──────────────────────────────────────────────
load_dotenv()
LINE_TOKEN      = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET     = os.getenv("LINE_CHANNEL_SECRET")
LINE_GROUP_ID   = "C1d9ed412f2141da57e47bd28cec532a4"  # ←自身のグループ ID

# ngrok URL は毎回ファイルから読む（無ければ .env のまま）
UNIV_SERVER_ENDPOINT = os.getenv("UNIV_SERVER_ENDPOINT", "")
if NGROK_FILE.exists():
    UNIV_SERVER_ENDPOINT = NGROK_FILE.read_text().strip() + "/record"

# ──────────────────────────────────────────────
# ③ Flask & LINE 初期化
# ──────────────────────────────────────────────
app     = Flask(__name__)
bot     = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)
JST     = timezone(timedelta(hours=9))

# ──────────────────────────────────────────────
# ④ 共通ヘルパ
# ──────────────────────────────────────────────
def log(*msg, **kw):
    print(*msg, **kw, file=sys.stderr, flush=True)

def safe_reply(text: str, event):
    try:
        bot.reply_message(event.reply_token, TextSendMessage(text=text))
    except LineBotApiError:
        pass  # 古い reply_token など

# ──────────────────────────────────────────────
# ⑤ Webhook 入口
# ──────────────────────────────────────────────
@app.before_request
def _debug_hit():
    if request.path == "/callback":
        log("🔔 /callback hit")

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except Exception as e:
        log("❌ Webhook handling error:", e)
        abort(400)
    return "OK"

# ──────────────────────────────────────────────
# ⑥ 画像 / 動画 メッセージ
# ──────────────────────────────────────────────
@handler.add(MessageEvent, message=(ImageMessage, VideoMessage))
def handle_media(event):
    # グループ / LINE 内メディアか確認
    if event.source.type != "group" or event.source.group_id != LINE_GROUP_ID:
        return
    if event.message.content_provider.type != "line":
        return

    now   = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    uid   = event.source.user_id
    log(f"📸 {uid=} {today=} {now.time()}")

    # 名前解決
    name = uid
    if MEMBERS_PATH.exists():
        try:
            name = json.loads(MEMBERS_PATH.read_text()).get(uid, uid)
        except Exception as e:
            log("⚠️ members.json 読み込み失敗:", e)

    # log.json へ追記（重複 1 日 1 回）
    logs = json.loads(LOG_PATH.read_text())
    logs.setdefault(name, [])
    if any(str(x).startswith(today) for x in logs[name]):
        safe_reply("すでに今日の投稿は受け取っています！", event)
        return
    logs[name].append(now.isoformat())
    LOG_PATH.write_text(json.dumps(logs, ensure_ascii=False, indent=2))
    log("✅ log.json 追記 OK")

    # 大学サーバーへ POST
    try:
        res = requests.post(
            UNIV_SERVER_ENDPOINT, json={"user_id": uid, "date": today}, timeout=5
        )
        log("📡 record.py status:", res.status_code, res.text[:120])
    except requests.exceptions.RequestException as e:
        log("❌ 大学サーバー送信失敗:", e)

    safe_reply("受け取りました！", event)

# ──────────────────────────────────────────────
# ⑦ テキスト メッセージ
# ──────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    txt = event.message.text.strip()
    if txt == "何が好き？":
        safe_reply("チョコミントよりもあ・な・た", event)
    elif txt.endswith("募"):
        safe_reply("🆑", event)
    elif txt.endswith("ちゃん！"):
        safe_reply("はーい", event)
    elif txt.endswith("ちんげのきたろう"):
        safe_reply("受け取りました：ちんげのきたろう", event)
    elif txt.endswith("ダディダディ"):
        safe_reply(f"どすこいわっしょいピーポーピーポ―{txt}～", event)
    elif txt.endswith("途中経過"):
        send_progress(txt.replace("途中経過", "").strip(), event)

# ──────────────────────────────────────────────
def send_progress(name: str, event):
    if not (MEMBERS_PATH.exists() and DAILY_CSV_PATH.exists()):
        safe_reply("データがありません。", event)
        return

    names = list(json.loads(MEMBERS_PATH.read_text()).values())
    if name not in names:
        safe_reply("その名前は登録されていません。", event)
        return

    idx   = names.index(name)
    rows  = csv.reader(DAILY_CSV_PATH.open(encoding="utf-8"))
    missed = sum(1 for r in rows if len(r) > idx and r[idx] == "1")
    safe_reply(f"{name}は今月{missed}回忘れてます", event)

# ──────────────────────────────────────────────
# ⑧ 補助ルート
# ──────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():          # Render ヘルスチェック
    return "LINE bot is alive"

@app.route("/files", methods=["GET"])
def list_files():     # Render デバッグ用
    return {"files": os.listdir(BASE_DIR)}

# ──────────────────────────────────────────────
if __name__ == "__main__":          # ローカルテスト用
    app.run(host="0.0.0.0", port=5000)
