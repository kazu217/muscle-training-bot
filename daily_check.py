import json, csv
from datetime import datetime, timedelta
import pytz

# タイムゾーンを日本時間に設定
JST = pytz.timezone("Asia/Tokyo")

# 昨日の 00:00 〜 23:59 の時間範囲
now = datetime.now(JST)
yesterday = (now - timedelta(days=1)).date()
start = JST.localize(datetime.combine(yesterday, datetime.min.time()))
end = JST.localize(datetime.combine(yesterday, datetime.max.time()))

# 🔹 メンバー情報の読み込み
with open("members.json", "r", encoding="utf-8") as f:
    id_to_name = json.load(f)

members = sorted([(id_to_name[uid], uid) for uid in id_to_name])

# 🔹 ログの読み込み
with open("log.json", "r", encoding="utf-8") as f:
    logs = json.load(f)

# 🔹 罰金対象リストを作成
row = []
for name, uid in members:
    timestamps = logs.get(uid, [])
    posted = False
    for t in timestamps:
        try:
            dt = datetime.fromisoformat(t).astimezone(JST)
            if start <= dt <= end:
                posted = True
                break
        except Exception as e:
            print(f"❌ {t} の日時変換に失敗: {e}")
    row.append(0 if posted else 1)

# 🔹 CSVに追記
with open("daily.csv", "a", newline='', encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(row)

print(f"✅ {yesterday} の記録を daily.csv に追加しました")
