#!/bin/zsh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_FILE="${NCM_ENV_FILE:-$REPO_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

ADDON="${NCM_ADDON:-$REPO_ROOT/mitmproxy/netease6_final.py}"
QR_FILE="${NCM_QR_FILE:-$HOME/ncm_qr_result.json}"
LOG_DIR="${NCM_LOG_DIR:-$HOME/Library/Logs}"
API_HOST="${NCM_API_HOST:-127.0.0.1}"
API_PORT="${NCM_API_PORT:-3000}"
PROXY_HOST="${NCM_PROXY_HOST:-0.0.0.0}"
PROXY_PORT="${NCM_PROXY_PORT:-8080}"
export NCM_COMPAT_CONFIG="${NCM_COMPAT_CONFIG:-$REPO_ROOT/config/config.json}"
API_LOG="$LOG_DIR/netease6-api.log"

API_STARTED=0
API_PID=""


echo
echo "======================================"
echo " NetEase Music 6 Compatibility Bridge"
echo "======================================"
echo


# ------------------------------------------------------------
# Check required files
# ------------------------------------------------------------

if [[ ! -f "$ADDON" ]]; then
    echo "ERROR: Missing $ADDON"
    exit 1
fi


if [[ ! -f "$QR_FILE" ]]; then
    echo "ERROR: Missing QR credential:"
    echo "$QR_FILE"
    exit 1
fi


chmod 600 "$QR_FILE"

mkdir -p "$LOG_DIR"


# ------------------------------------------------------------
# Check port 8080
# ------------------------------------------------------------

if lsof -nP \
    -iTCP:"$PROXY_PORT" \
    -sTCP:LISTEN \
    >/dev/null 2>&1
then
    echo "ERROR: TCP $PROXY_PORT is already in use."
    echo
    echo "If an old mitmweb is running,"
    echo "press Ctrl+C in that terminal first."
    exit 1
fi


# ------------------------------------------------------------
# Start local NCM API when necessary
# ------------------------------------------------------------

if nc -z "$API_HOST" "$API_PORT" \
    >/dev/null 2>&1
then

    echo "[OK] NCM API already running on $API_HOST:$API_PORT"

else

    echo "[..] Starting NCM API..."

    npx -y \
        @neteasecloudmusicapienhanced/api@latest \
        >"$API_LOG" \
        2>&1 &

    API_PID=$!
    API_STARTED=1

    READY=0

    for i in {1..30}
    do
        if nc -z "$API_HOST" "$API_PORT" \
            >/dev/null 2>&1
        then
            READY=1
            break
        fi

        sleep 1
    done

    if [[ "$READY" -ne 1 ]]; then
        echo "ERROR: NCM API did not start."
        echo
        echo "Log:"
        echo "$API_LOG"

        if [[ -n "$API_PID" ]]; then
            kill "$API_PID" \
                >/dev/null 2>&1 || true
        fi

        exit 1
    fi

    echo "[OK] NCM API ready on :3000"

fi


# ------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------

cleanup() {

    echo
    echo "[..] Shutting down..."

    if [[ "$API_STARTED" -eq 1 ]] \
        && [[ -n "$API_PID" ]]
    then
        kill "$API_PID" \
            >/dev/null 2>&1 || true
    fi

}


trap cleanup EXIT INT TERM HUP


# ------------------------------------------------------------
# Start mitmproxy
# ------------------------------------------------------------

echo "[OK] QR login credential loaded"
echo "[OK] TLS 1.0 client compatibility enabled"
echo "[OK] Global appver spoof enabled"
echo "[OK] QR auth-cookie injection enabled"
echo
echo "HTC proxy:"
echo "  Listen : $PROXY_HOST:$PROXY_PORT"
echo
echo "Press Ctrl+C to stop."
echo


mitmweb \
    --listen-host "$PROXY_HOST" \
    --listen-port "$PROXY_PORT" \
    --set tls_version_client_min=TLS1 \
    -s "$ADDON"
