import json, csv, datetime

# 🔸 1. ユーザーID → 表示名マッピングを読み込む
with open("members.json", "r", encoding="utf-8") as f:
    id_to_name = json.load(f)

# 🔸 2. (表示名, user_id) のリストを作成
members = [(id_to_name[uid], uid) for uid in id_to_name]

# 🔸 3. log.json から昨日のデータを取得
with open("log.json", "r", encoding="utf-8") as f:
    logs = json.load(f)

yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
day_log = logs.get(yesterday, [])

# 🔸 4. 出力行を作成（投稿していれば0、していなければ1）
row = [0 if uid in day_log else 1 for _, uid in members]

# 🔸 5. CSVに追加
with open("daily.csv", "a", newline='', encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(row)

print(f"✅ {yesterday} の記録を daily.csv に追加しました")
