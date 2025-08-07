#!/usr/bin/env bash
#
# watch_ngrok.sh ─ ngrok URL を監視し Render の環境変数を自動更新
#───────────────────────────────────────────────
# - tmux で `ngrok http 5000` をバックグラウンド常駐させる
# - http://localhost:4040/api/tunnels から https URL を grep/sed で抽出
# - URL が変わったら Render CLI で NGROK_RECORD_URL を更新
#
# 必要:
#   ▸ tmux
#   ▸ ngrok     (~/musclebot/ngrok など実行可能パスに置く)
#   ▸ render-cli (npm i -g render-cli)
#
# 必須環境変数:
#   RENDER_API_KEY   … Render Personal API Key
#
# 任意環境変数:
#   RENDER_SERVICE   … Render のサービス名 (デフォルト: muscle-training-bot)
#───────────────────────────────────────────────

set -euo pipefail

# ───────── 設定 ─────────
PORT=5000                           # Flask / record.py が listen しているポート
SESSION_NAME="ngrok"                # tmux セッション名
API_URL="http://127.0.0.1:4040/api/tunnels"
URL_FILE="$(dirname "$0")/current_ngrok_url.txt"

RENDER_SERVICE="${RENDER_SERVICE:-muscle-training-bot}"
NGROK_BIN="${NGROK_BIN:-./ngrok}"   # パスを変えたい場合は環境変数で上書き
CURL_OPTS="-s --max-time 5 --connect-timeout 3"

timestamp() { date '+[%F %T]'; }

log() { echo "$(timestamp) $*"; }

# ───────── 1) ngrok が走っていなければ起動 ─────────
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  log "🔄 ngrok セッションが無いので起動します"
  tmux new-session -d -s "$SESSION_NAME" "$NGROK_BIN" http "$PORT"
  # ngrok API が上がるまで少し待機
  sleep 5
fi

# ───────── 2) 最新 public_url を取得 (jq 不使用) ─────────
PUB_URL=$(
  curl $CURL_OPTS "$API_URL" 2>/dev/null \
  | grep -oE '"public_url":"https:[^"]+"' \
  | head -n1 | cut -d'"' -f4
)

if [[ -z "$PUB_URL" ]]; then
  log "❌ ngrok の公開 URL を取得できません"
  exit 1
fi

# ───────── 3) 変化チェック ─────────
OLD_URL="$(cat "$URL_FILE" 2>/dev/null || true)"

if [[ "$PUB_URL" != "$OLD_URL" ]]; then
  log "🔄 URL 変更検出: $OLD_URL → $PUB_URL"
  echo "$PUB_URL" > "$URL_FILE"

  if [[ -z "${RENDER_API_KEY:-}" ]]; then
    log "⚠️  RENDER_API_KEY が未設定。Render への反映をスキップしました"
    exit 0
  fi

  # Render CLI で環境変数を更新
  render env:set NGROK_RECORD_URL="$PUB_URL" --service "$RENDER_SERVICE" \
    >/dev/null 2>&1 && \
    log "✅ Render 環境変数 NGROK_RECORD_URL を更新しました" || \
    log "❌ Render 環境変数の更新に失敗しました"

else
  log "✅ URL 変更なし ($PUB_URL)"
fi
