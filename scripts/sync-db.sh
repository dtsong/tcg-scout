#!/usr/bin/env bash
set -euo pipefail

BUCKET="gs://tcg-scout-data"
DATA_DIR="$(cd "$(dirname "$0")/../data" && pwd)"

usage() {
  echo "Usage: $0 <pull|push> [format]"
  echo ""
  echo "  pull [format]  Download DB(s) from GCS to data/"
  echo "  push [format]  Checkpoint WAL and upload DB(s) to GCS"
  echo ""
  echo "If format is omitted, syncs all .db files."
  echo "Examples:"
  echo "  $0 pull                  # pull all DBs"
  echo "  $0 push nihil-zero       # push nihil-zero.db only"
  exit 1
}

checkpoint_wal() {
  local db_path="$1"
  python3 - "$db_path" <<'PYEOF'
import sqlite3, sys
db_path = sys.argv[1]
c = sqlite3.connect(db_path)
busy, log, checkpointed = c.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
c.close()
if busy:
    print(f"ERROR: WAL checkpoint failed for {db_path} (busy={busy})", file=sys.stderr)
    sys.exit(1)
print(f"WAL checkpoint OK: {log} pages logged, {checkpointed} checkpointed")
PYEOF
}

pull() {
  local format="${1:-}"
  if [ -n "$format" ]; then
    echo "Pulling ${format}.db from GCS..."
    gsutil cp "${BUCKET}/${format}.db" "${DATA_DIR}/${format}.db"
  else
    echo "Pulling all DBs from GCS..."
    gsutil -m cp "${BUCKET}/*.db" "${DATA_DIR}/"
  fi
  echo "Done."
}

push() {
  local format="${1:-}"
  if [ -n "$format" ]; then
    local db_path="${DATA_DIR}/${format}.db"
    if [ ! -f "$db_path" ]; then
      echo "Error: ${db_path} not found" >&2
      exit 1
    fi
    echo "Checkpointing WAL for ${format}.db..."
    checkpoint_wal "$db_path"
    echo "Pushing ${format}.db to GCS..."
    gsutil cp "$db_path" "${BUCKET}/${format}.db"
  else
    for db_path in "${DATA_DIR}"/*.db; do
      [ -f "$db_path" ] || continue
      local name
      name="$(basename "$db_path")"
      echo "Checkpointing WAL for ${name}..."
      checkpoint_wal "$db_path"
    done
    echo "Pushing all DBs to GCS..."
    gsutil -m cp "${DATA_DIR}"/*.db "${BUCKET}/"
  fi
  echo "Done."
}

[ $# -lt 1 ] && usage

case "$1" in
  pull) pull "${2:-}" ;;
  push) push "${2:-}" ;;
  *) usage ;;
esac
