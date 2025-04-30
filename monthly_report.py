import csv, os
from linebot import LineBotApi
from linebot.models import TextSendMessage

members = ["うり", "ともや", "りょうや", "ほうろう", "いなうた", "じおん"]
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
group_id = os.getenv("LINE_GROUP_ID")

with open("daily.csv") as f:
    rows = list(csv.reader(f))

N = len(members)
days = len(rows)
meibo = [0] * N

for i in range(days):
    fine = sum(int(x) for x in rows[i])
    exclude = 0  # 今は考慮しない
    amount = 200 * fine / (N - fine) if (N - fine) > 0 else 0

    for j in range(N):
        v = int(rows[i][j])
        if v == 0:
            meibo[j] += amount
        else:
            meibo[j] -= 200

result = "\n".join(f"{members[i]}: {meibo[i]:.2f}円" for i in range(N))
line_bot_api.push_message(group_id, TextSendMessage(text=result))
