from pathlib import Path
BASE = Path(__file__).resolve().parent

from flask import Flask, request, jsonify
import json, os
from datetime import datetime
from linebot import LineBotApi
from dotenv import load_dotenv
load_dotenv()

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
app = Flask(__name__)

@app.route("/record", methods=["POST"])
def record():
    data = request.get_json()
    user_id = data.get("user_id")
    timestamp = datetime.now().isoformat()

    if not user_id:
        return jsonify({"error": "invalid data"}), 400

    log_file = BASE / "log.json"
    logs = {}

    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)

    if user_id not in logs:
        logs[user_id] = []
    logs[user_id].append(timestamp)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
