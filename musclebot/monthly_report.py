import csv
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path
from linebot import LineBotApi
from linebot.models import TextSendMessage

BASE = Path(__file__).resolve().parent
load_dotenv()

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
group_id = os.getenv("LINE_GROUP_ID")

auto_mode = os.getenv("AUTO_MONTHLY") == "1"

with open(BASE / "members.json", "r", encoding="utf-8") as f:
    id_to_name = json.load(f)

user_ids = list(id_to_name.keys())
member_names = [id_to_name[uid] for uid in user_ids]
N = len(user_ids)

with open(BASE / "daily.csv", "r", encoding="utf-8") as f:
    rows = list(csv.reader(f))

days = len(rows)
meibo = [0] * N

for i, day in enumerate(rows, 1):
    if len(day) != N:
        print(f"️ スキップ: day {i} の列数が不一致（{len(day)}列、想定は {N}列）")
        continue

    fine_cnt = sum(1 for v in day if int(v) == 1)
    exclude_cnt = sum(1 for v in day if int(v) == 2)

    if (N - fine_cnt - exclude_cnt) > 0:
        amount = 200 * fine_cnt / (N - fine_cnt - exclude_cnt)
    else:
        amount = 0

    for j, v in enumerate(map(int, day)):
        if v == 0:
            meibo[j] += amount
        elif v == 1:
            meibo[j] -= 200

lines = [f"{member_names[i]}: {meibo[i]:.2f}円" for i in range(N)]

if auto_mode:
    last_month_date = datetime.now().replace(day=1) - timedelta(days=1)
    month_title = last_month_date.strftime("%-m月総計")
    result_text = month_title + "\n" + "\n".join(lines)
else:
    result_text = "\n".join(lines)

print(f" 送信先: {group_id}")
print(" 送信内容:")
print(result_text)

try:
    line_bot_api.push_message(group_id, TextSendMessage(text=result_text))
    print(" 罰金結果をLINEに送信しました")
except Exception as e:
    print("❌ LINEへの送信に失敗しました:", e)

if auto_mode:
    with open(BASE / "daily.csv", "w", encoding="utf-8", newline='') as f:
        pass
    print("️ 自動実行モード：daily.csv を初期化しました")
