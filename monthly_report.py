import csv
import os
import json
from dotenv import load_dotenv
from linebot import LineBotApi
from linebot.models import TextSendMessage
from dotenv import load_dotenv
load_dotenv()


# ✅ .env の読み込み（必要）
load_dotenv()

# ✅ 環境変数からLINE情報を取得
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
group_id = os.getenv("LINE_GROUP_ID")

# ✅ メンバー情報を取得（順序保持）
with open("members.json", "r", encoding="utf-8") as f:
    id_to_name = json.load(f)

user_ids = list(id_to_name.keys())
member_names = [id_to_name[uid] for uid in user_ids]
N = len(user_ids)

# ✅ daily.csv を読み込み
with open("daily.csv", "r", encoding="utf-8") as f:
    rows = list(csv.reader(f))

days = len(rows)
meibo = [0] * N  # 各人の罰金記録

# ✅ 日毎に計算
for i in range(days):
    day = rows[i]
    if len(day) != N:
        print(f"⚠️ スキップ: day {i+1} の列数が不一致（{len(day)}列、想定は {N}列）")
        continue

    fine = sum(int(x) for x in day)
    exclude = 0  # 将来用

    if (N - fine - exclude) > 0:
        amount = 200 * fine / (N - fine - exclude)
    else:
        amount = 0

    for j in range(N):
        v = int(day[j])
        if v == 0:
            meibo[j] += amount
        elif v == 1:
            meibo[j] -= 200

# ✅ 結果を整形
result_lines = [f"{member_names[i]}: {meibo[i]:.2f}円" for i in range(N)]
result_text = "\n".join(result_lines)

# ✅ デバッグ出力
print(f"📤 送信先: {group_id}")
print("🔽 送信内容:")
print(result_text)

# ✅ LINEグループに送信
try:
    line_bot_api.push_message(group_id, TextSendMessage(text=result_text))
    print("✅ 罰金結果をLINEに送信しました")
except Exception as e:
    print("❌ LINEへの送信に失敗しました:", e)
