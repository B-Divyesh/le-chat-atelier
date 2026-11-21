#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ "$(curl -fsS --max-time 4 http://127.0.0.1:8090/health 2>/dev/null || true)" != ready ]]; then
  ssh -fNT -o BatchMode=yes -o ExitOnForwardFailure=yes -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
    -L 127.0.0.1:8090:127.0.0.1:8090 -p "${ATELIER_SSH_PORT:-22}" "${ATELIER_SSH_HOST:?Set ATELIER_SSH_HOST to the user@host for your GPU server}"
fi
if ! curl -fsS --max-time 3 http://127.0.0.1:8765/studio.js >/dev/null 2>&1; then
  launchctl submit -l local.lechatatelier.studio \
    -o /tmp/le-chat-atelier-studio.log -e /tmp/le-chat-atelier-studio.log \
    -- "$(command -v python3)" -u "$PWD/local_studio.py"
  for attempt in {1..40}; do
    curl -fsS --max-time 2 http://127.0.0.1:8765/studio.js >/dev/null 2>&1 && break
    sleep 0.25
  done
fi
curl -fsS http://127.0.0.1:8765/studio.js >/dev/null
open -a Helium http://127.0.0.1:8765/
