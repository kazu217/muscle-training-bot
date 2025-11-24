<<<<<<< HEAD
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

#  メンバー情報の読み込み
with open("members.json", "r", encoding="utf-8") as f:
    id_to_name = json.load(f)

members = [(id_to_name[uid], uid) for uid in id_to_name]   # ←順序保持！！

#  ログの読み込み
with open("log.json", "r", encoding="utf-8") as f:
    logs = json.load(f)

#  罰金対象リストを作成
row = []
for name, uid in members:
    posted = False
    for t in logs.get(uid, []):
        try:
            dt = datetime.fromisoformat(t)
            if dt.tzinfo is None:
                dt = JST.localize(dt)
            else:
                dt = dt.astimezone(JST)
            if start <= dt <= end:
                posted = True
                break
        except Exception as e:
            print(f"❌ {t} 変換失敗: {e}")
    row.append(0 if posted else 1)

#  CSVに追記
with open("daily.csv", "a", newline='', encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(row)

print(f" {yesterday} の記録を daily.csv に追加しました")
=======
# -*- coding: utf-8 -*-
"""
daily_check.py – 前日の投稿有無を daily.csv に追記
"""

from pathlib import Path
from datetime import datetime, timedelta
import json, csv, pytz

BASE = Path(__file__).resolve().parent

LOG_PATH     = BASE / "log.json"
MEMBERS_PATH = BASE / "members.json"
CSV_PATH     = BASE / "daily.csv"

# ───────────── JST 昨日
JST   = pytz.timezone("Asia/Tokyo")
today = datetime.now(JST).date()
ydate = today - timedelta(days=1)
start = JST.localize(datetime.combine(ydate, datetime.min.time()))
end   = JST.localize(datetime.combine(ydate, datetime.max.time()))

# ───────────── データ読込
id_to_name = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))

# log.json が無ければ空 dict
if LOG_PATH.exists():
    logs = json.loads(LOG_PATH.read_text(encoding="utf-8"))
else:
    logs = {}

members = [(uid, id_to_name[uid]) for uid in id_to_name]   # 順序保持

# ───────────── 判定
row = []
for uid, name in members:
    posted = False
    for entry in logs.get(name, []):
        try:
            # entry は {"date": "...", "ts": "..."}
            ts = entry.get("ts")
            if not ts:
                continue
            dt = datetime.fromisoformat(ts)
            dt = (dt if dt.tzinfo else JST.localize(dt)).astimezone(JST)
            if start <= dt <= end:
                posted = True
                break
        except Exception as e:
            print(f"[WARN] 時刻変換失敗: {entry} ({e})")
    row.append(0 if posted else 1)

# ───────────── 追記
with CSV_PATH.open("a", newline='', encoding="utf-8") as f:
    csv.writer(f).writerow(row)

print(f"[{ydate}] の結果を {CSV_PATH.name} に追記しました: {row}")
>>>>>>> ローカルの変更を保存
