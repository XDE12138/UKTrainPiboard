#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${1:-pi-rail@192.168.31.242}"
LOCAL_ROOT="${PIBOARD_LOCAL_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REMOTE_ROOT="${PIBOARD_REMOTE_ROOT:-/home/pi-rail/CC-UK-TR/piboard}"
SERVICE_NAME="${PIBOARD_SERVICE_NAME:-piboard.service}"

echo "Stopping ${SERVICE_NAME} on ${PI_HOST}"
ssh "${PI_HOST}" "sudo systemctl stop '${SERVICE_NAME}'"

echo "Syncing ${LOCAL_ROOT} to ${PI_HOST}:${REMOTE_ROOT}"
rsync -az \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  --exclude 'review_artifacts' \
  --exclude '*.pyc' \
  "${LOCAL_ROOT}/" \
  "${PI_HOST}:${REMOTE_ROOT}/"

echo "Validating synced files"
ssh "${PI_HOST}" "\
  PYTHONPYCACHEPREFIX=/tmp/piboard-pycache python3 -m compileall -q '${REMOTE_ROOT}' && \
  python3 -m json.tool '${REMOTE_ROOT}/data/state.json' >/dev/null"

echo "Installing service file and starting ${SERVICE_NAME}"
ssh "${PI_HOST}" "\
  sudo cp '${REMOTE_ROOT}/deployment/piboard-kmsdrm.service' /etc/systemd/system/piboard.service && \
  sudo systemctl daemon-reload && \
  sudo systemctl start '${SERVICE_NAME}' && \
  systemctl status '${SERVICE_NAME}' --no-pager"

echo "Waiting for local PiBoard API"
for attempt in {1..20}; do
  if ssh "${PI_HOST}" "curl -fsS http://127.0.0.1:8080/api/device-status" 2>/dev/null; then
    echo
    exit 0
  fi
  sleep 1
done

echo "PiBoard API did not respond on 127.0.0.1:8080 after 20 seconds" >&2
exit 1
