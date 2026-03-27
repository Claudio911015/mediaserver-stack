#!/bin/bash
# arr_watchdog.sh — Monitor and auto-restart Docker containers
# Runs as a systemd service, loops every 60s

CHECK_INTERVAL=60
LOG_FILE="/var/log/arr_watchdog.log"
MAX_LOG_SIZE=10485760   # 10 MB, then rotate

# Services with HTTP health check endpoints
# Use "skip" for headless containers (no web UI)
declare -A SERVICES=(
    [radarr]="http://localhost:7878/ping"
    [sonarr]="http://localhost:8989/ping"
    [lidarr]="http://localhost:8686/ping"
    [prowlarr]="http://localhost:9696/ping"
    [bazarr]="http://localhost:6767"
    [tautulli]="http://localhost:8181/status"
    [lidify]="http://localhost:5055"
    [decluttarr]="skip"
    [unpackerr]="skip"
    [kometa]="skip"
)

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"; }

rotate_log() {
    if [[ -f "$LOG_FILE" && $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"; log "Log rotated"
    fi
}

check_service() {
    local name=$1 url=$2
    local state
    state=$(docker inspect --format '{{.State.Running}}' "$name" 2>/dev/null)
    [[ "$state" != "true" ]] && return 2    # not running
    [[ "$url" == "skip" ]] && return 0       # headless, just check state
    curl -sf --max-time 10 "$url" > /dev/null 2>&1 && return 0 || return 1
}

restart_service() {
    local name=$1
    log "Restarting $name..."
    docker restart "$name" > /dev/null 2>&1 && sleep 20 && log "$name restarted OK" || log "ERROR: could not restart $name"
}

monitor() {
    local check_count=0
    log "Watchdog started — services: ${!SERVICES[*]}"
    while true; do
        rotate_log
        ((check_count++))
        for name in "${!SERVICES[@]}"; do
            check_service "$name" "${SERVICES[$name]}"
            case $? in
                1) log "WARNING: $name not responding to HTTP — restarting..."; restart_service "$name" ;;
                2) log "WARNING: $name not running — starting..."; docker start "$name" > /dev/null 2>&1 && sleep 20 && log "$name started" || log "ERROR: could not start $name" ;;
            esac
        done
        [[ $((check_count % 10)) -eq 0 ]] && log "OK — checks: $check_count"
        sleep $CHECK_INTERVAL
    done
}

show_status() {
    echo "=== CONTAINER STATUS ==="
    for name in radarr sonarr lidarr prowlarr bazarr tautulli lidify decluttarr unpackerr kometa; do
        state=$(docker inspect --format '{{.State.Status}}' "$name" 2>/dev/null || echo "not found")
        printf "  %-15s %s\n" "$name" "$state"
    done
    echo ""; echo "=== RECENT LOG ==="
    tail -20 "$LOG_FILE" 2>/dev/null || echo "No log"
}

trap 'log "Watchdog stopped"; exit 0' SIGINT SIGTERM

case "${1:-}" in
    start)  monitor ;;
    status) show_status ;;
    *)      echo "Usage: $0 {start|status}" ;;
esac
