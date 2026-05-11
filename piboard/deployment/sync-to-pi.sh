#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  PI_HOST="$1"
elif [[ -n "${PIBOARD_PI_HOST:-}" ]]; then
  PI_HOST="${PIBOARD_PI_HOST}"
else
  echo "Usage: $0 <pi-user@pi-host-or-ip>" >&2
  echo "Or set PIBOARD_PI_HOST=<pi-user@pi-host-or-ip>." >&2
  exit 2
fi

LOCAL_ROOT="${PIBOARD_LOCAL_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
if [[ "${PI_HOST}" != *@* && -z "${PIBOARD_REMOTE_ROOT:-}" ]]; then
  echo "PI_HOST must include a user, for example pi@<pi-host>." >&2
  echo "Alternatively set PIBOARD_REMOTE_ROOT explicitly." >&2
  exit 2
fi

REMOTE_USER="${PI_HOST%@*}"
REMOTE_ROOT="${PIBOARD_REMOTE_ROOT:-/home/${REMOTE_USER}/CC-UK-TR/piboard}"
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

SERVICE_TEMPLATE="${LOCAL_ROOT}/deployment/piboard-kmsdrm.service"
SERVICE_TMP="$(mktemp)"
trap 'rm -f "${SERVICE_TMP}"' EXIT
sed \
  -e "s|^User=.*|User=${REMOTE_USER}|" \
  -e "s|^WorkingDirectory=.*|WorkingDirectory=${REMOTE_ROOT}|" \
  -e "s|^ExecStart=/usr/bin/python3 .*main.py|ExecStart=/usr/bin/python3 ${REMOTE_ROOT}/main.py|" \
  "${SERVICE_TEMPLATE}" > "${SERVICE_TMP}"

echo "Installing service file and starting ${SERVICE_NAME}"
rsync -az "${SERVICE_TMP}" "${PI_HOST}:/tmp/piboard.service"
ssh "${PI_HOST}" "\
  sudo cp /tmp/piboard.service /etc/systemd/system/piboard.service && \
  rm -f /tmp/piboard.service && \
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
