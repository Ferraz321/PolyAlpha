#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
for pidfile in run/*.pid; do
  [[ -e "$pidfile" ]] || {
    echo "no pid files"
    exit 0
  }
  name="$(basename "$pidfile" .pid)"
  pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "$name running pid=$pid"
  else
    echo "$name stopped pid=$pid"
  fi
done
