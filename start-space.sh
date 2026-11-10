#!/bin/sh
set -eu

export API_URL=http://127.0.0.1:8000
export DB_PATH=/tmp/invoices.db
export DEMO_MODE=1
export USE_VECTOR=0
export HOME=/tmp

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!
ui_pid=

cleanup() {
    if [ -n "$ui_pid" ]; then
        kill "$ui_pid" 2>/dev/null || true
    fi
    kill "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

attempt=0
until python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=1)" 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        echo "API failed to become healthy" >&2
        exit 1
    fi
    sleep 1
done

streamlit run ui/streamlit_app.py --server.port 7860 --server.address 0.0.0.0 --server.headless true &
ui_pid=$!
wait "$ui_pid"
