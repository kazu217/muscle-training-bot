import json, csv, datetime

members = [
    ("うり", "user_id_1"),
    ("ともや", "user_id_2"),
    ("りょうや", "user_id_3"),
    ("ほうろう", "user_id_4"),
    ("いなうた", "user_id_5"),
    ("じおん", "user_id_6"),
]

with open("log.json") as f:
    logs = json.load(f)

today = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
day_log = logs.get(today, [])

row = []
for name, uid in members:
    row.append(0 if uid in day_log else 1)

with open("daily.csv", "a", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(row)
