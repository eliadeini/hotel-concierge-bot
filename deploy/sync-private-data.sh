#!/usr/bin/env bash
# Mirrors app/knowledge/files/ and app/knowledge/hotel_skills/ to the
# server over SSH, bypassing GitHub (some files in there are gitignored
# real client data — see .gitignore). Run after editing a knowledge file.
#
# Usage: deploy/sync-private-data.sh [--dry-run] [--host H] [--user U] [--key PATH]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REMOTE_BASE="/home/ubuntu/hotel-concierge-bot"

DRY_RUN=false
CLI_HOST=""
CLI_USER=""
CLI_KEY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --host) CLI_HOST="$2"; shift 2 ;;
    --user) CLI_USER="$2"; shift 2 ;;
    --key) CLI_KEY="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--dry-run] [--host H] [--user U] [--key PATH]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Local config file (gitignored) — see deploy/sync-private-data.env.example.
if [[ -f "$SCRIPT_DIR/sync-private-data.env" ]]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/sync-private-data.env"
fi

EC2_HOST="${CLI_HOST:-${EC2_HOST:-}}"
EC2_USER="${CLI_USER:-${EC2_USER:-ubuntu}}"
EC2_SSH_KEY_PATH="${CLI_KEY:-${EC2_SSH_KEY_PATH:-}}"

if [[ -z "$EC2_HOST" ]]; then
  echo "ERROR: no server host configured." >&2
  echo "Copy deploy/sync-private-data.env.example to deploy/sync-private-data.env" >&2
  echo "and set EC2_HOST, or pass --host <host>." >&2
  exit 1
fi

SSH_OPTS=()
if [[ -n "$EC2_SSH_KEY_PATH" ]]; then
  SSH_OPTS+=(-i "$EC2_SSH_KEY_PATH")
fi

SOURCE_DIRS=("app/knowledge/files" "app/knowledge/hotel_skills")

LOCAL_FILES=()
REMOTE_FILES=()
for dir in "${SOURCE_DIRS[@]}"; do
  local_dir="$REPO_DIR/$dir"
  [[ -d "$local_dir" ]] || continue
  while IFS= read -r -d '' local_path; do
    LOCAL_FILES+=("$local_path")
    REMOTE_FILES+=("$REMOTE_BASE/${local_path#"$REPO_DIR/"}")
  done < <(find "$local_dir" -type f -print0)
done

if [[ ${#LOCAL_FILES[@]} -eq 0 ]]; then
  echo "ERROR: no files found under ${SOURCE_DIRS[*]} — nothing to sync." >&2
  exit 1
fi

if $DRY_RUN; then
  echo "Dry run — would sync:"
  for i in "${!LOCAL_FILES[@]}"; do
    echo "  ${LOCAL_FILES[$i]} -> $EC2_USER@$EC2_HOST:${REMOTE_FILES[$i]}"
  done
  exit 0
fi

# Batch-create every needed remote directory in a single SSH round trip.
declare -A SEEN_DIRS
REMOTE_DIRS=()
for rf in "${REMOTE_FILES[@]}"; do
  d="$(dirname "$rf")"
  if [[ -z "${SEEN_DIRS[$d]:-}" ]]; then
    SEEN_DIRS[$d]=1
    REMOTE_DIRS+=("$d")
  fi
done

MKDIR_ARGS=""
for d in "${REMOTE_DIRS[@]}"; do
  MKDIR_ARGS+=" $(printf '%q' "$d")"
done
ssh "${SSH_OPTS[@]}" "$EC2_USER@$EC2_HOST" "mkdir -p$MKDIR_ARGS"

for i in "${!LOCAL_FILES[@]}"; do
  lf="${LOCAL_FILES[$i]}"
  rf="${REMOTE_FILES[$i]}"
  echo "Syncing ${lf#"$REPO_DIR/"} ..."
  # Stream via ssh+cat rather than scp or rsync: scp's remote-path quoting
  # is unreliable for paths with spaces (e.g. the Hebrew region directory
  # names under app/knowledge/files/), and both scp and rsync would copy
  # this machine's CRLF line endings verbatim, corrupting any file that's
  # also tracked in git (which stores LF). sed strips the trailing \r.
  sed 's/\r$//' "$lf" | ssh "${SSH_OPTS[@]}" "$EC2_USER@$EC2_HOST" "cat > $(printf '%q' "$rf")"
done

echo
echo "Sync complete — no service restart needed, these files are read fresh from disk on every request."
