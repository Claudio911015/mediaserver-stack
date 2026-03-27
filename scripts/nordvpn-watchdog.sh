#!/bin/bash
# nordvpn-watchdog.sh — Keeps NordVPN connected with auto-reconnect + Telegram alerts
# Deploy on pihole-node as a systemd service

TELEGRAM_TOKEN="${TELEGRAM_BOT_TOKEN}"   # set via env or replace with your token
CHAT_ID="${TELEGRAM_CHAT_ID}"            # set via env or replace with your chat ID
LOG="/var/log/nordvpn-watchdog.log"
MAX_RETRIES=3
RETRY_INTERVAL=30       # seconds between retries
CHECK_INTERVAL=30       # seconds between normal checks
FALLBACK_RETRY=900      # seconds before retrying after all retries fail (15 min)

STATE_FILE="/tmp/nordvpn-watchdog-state"
FALLBACK_SINCE_FILE="/tmp/nordvpn-fallback-since"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

telegram() {
    local msg="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        -d text="NordVPN Pi: ${msg}" \
        -d parse_mode="Markdown" > /dev/null 2>&1
}

vpn_connected() { nordvpn status 2>/dev/null | grep -q "Status: Connected"; }

get_state() { cat "$STATE_FILE" 2>/dev/null || echo "UNKNOWN"; }
set_state() { echo "$1" > "$STATE_FILE"; }

log "=== NordVPN Watchdog started ==="
set_state "CHECKING"

while true; do
    if vpn_connected; then
        if [[ "$(get_state)" != "CONNECTED" ]]; then
            log "VPN connected"
            set_state "CONNECTED"
            rm -f "$FALLBACK_SINCE_FILE"
        fi
    else
        log "VPN disconnected — attempting reconnect..."
        telegram "VPN disconnected, reconnecting..."
        set_state "RECONNECTING"

        reconnected=false
        for i in $(seq 1 $MAX_RETRIES); do
            log "Reconnect attempt $i/$MAX_RETRIES..."
            nordvpn connect 2>/dev/null
            sleep $RETRY_INTERVAL
            if vpn_connected; then
                reconnected=true
                break
            fi
        done

        if $reconnected; then
            log "VPN reconnected successfully"
            telegram "VPN reconnected"
            set_state "CONNECTED"
            rm -f "$FALLBACK_SINCE_FILE"
        else
            log "ERROR: could not reconnect after $MAX_RETRIES attempts"
            telegram "ERROR: VPN reconnection failed. Retrying in 15 min."
            set_state "FALLBACK"
            if [[ ! -f "$FALLBACK_SINCE_FILE" ]]; then
                date +%s > "$FALLBACK_SINCE_FILE"
            fi
            sleep $FALLBACK_RETRY
            continue
        fi
    fi
    sleep $CHECK_INTERVAL
done
