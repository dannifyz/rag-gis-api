#!/usr/bin/env bash
set -euo pipefail

nginx -g 'daemon off;' &
nginx_pid=$!

uv run --no-sync rag-gis-api &
app_pid=$!

shutdown() {
    kill -TERM "$nginx_pid" "$app_pid" 2>/dev/null || true
}
trap shutdown SIGTERM SIGINT

wait -n "$nginx_pid" "$app_pid"
shutdown
wait
