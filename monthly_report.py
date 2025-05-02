import csv
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from linebot import LineBotApi
from linebot.models import TextSendMessage

load_dotenv()

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
group_id = os.getenv("LINE_GROUP_ID")

#  実行モード判定（自動実行か手動か）
auto_mode = os.getenv("AUTO_MONTHLY") == "1"

#  メンバー情報を取得（順序保持）
with open("members.json", "r", encoding="utf-8") as f:
    id_to_name = json.load(f)

user_ids = list(id_to_name.keys())
member_names = [id_to_name[uid] for uid in user_ids]
N = len(user_ids)

#  daily.csv を読み込み
with open("daily.csv", "r", encoding="utf-8") as f:
    rows = list(csv.reader(f))

days = len(rows)
meibo = [0] * N  # 各人の罰金記録

#  日毎に計算
for i, day in enumerate(rows, 1):
    if len(day) != N:
        print(f"️ スキップ: day {i} の列数が不一致（{len(day)}列、想定は {N}列）")
        continue

    # 罰金人数と除外人数をカウント
    fine_cnt     = sum(1 for v in day if int(v) == 1)
    exclude_cnt  = sum(1 for v in day if int(v) == 2)

    # 配当額（受け取る金額／人）
    if (N - fine_cnt - exclude_cnt) > 0:
        amount = 200 * fine_cnt / (N - fine_cnt - exclude_cnt)
    else:
        amount = 0

    # メンバー別累計
    for j, v in enumerate(map(int, day)):
        if v == 0:
            meibo[j] += amount         # 配当を受け取る
        elif v == 1:
            meibo[j] -= 200            # 罰金を払う
        # v == 2 のときは何もしない

#  結果テキスト整形
lines = [f"{member_names[i]}: {meibo[i]:.2f}円" for i in range(N)]

if auto_mode:
    from datetime import timedelta
    last_month_date = datetime.now().replace(day=1) - timedelta(days=1)
    month_title = last_month_date.strftime("%-m月総計")  # 前月
    result_text = month_title + "\n" + "\n".join(lines)
else:
    result_text = "\n".join(lines)


#  送信
print(f" 送信先: {group_id}")
print(" 送信内容:")
print(result_text)

try:
    line_bot_api.push_message(group_id, TextSendMessage(text=result_text))
    print(" 罰金結果をLINEに送信しました")
except Exception as e:
    print("❌ LINEへの送信に失敗しました:", e)

#  自動実行時は daily.csv を初期化
if auto_mode:
    with open("daily.csv", "w", encoding="utf-8", newline='') as f:
        pass  # 空で初期化
    print("️ 自動実行モード：daily.csv を初期化しました")
