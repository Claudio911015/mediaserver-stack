#!/bin/bash
# qbittorrent-temp-controller.sh — Pauses qBittorrent if CPU temperature exceeds threshold
# Resumes when temperature drops. Runs as a systemd service.

QBITTORRENT_PROCESS="qbittorrent-nox"
TEMP_THRESHOLD=90       # Max allowed CPU temp in Celsius
CHECK_INTERVAL=10       # Seconds between checks
LOG_FILE="/var/log/qbittorrent-temp.log"
MAX_PAUSE_TIME=120      # Max seconds paused before forced resume

paused=false
pause_start=0

log_message() { echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"; }

get_cpu_temperature() {
    local temp
    # Intel: Package id
    if sensors 2>/dev/null | grep -q "Package id"; then
        temp=$(sensors | grep "Package id" | awk '{print $4}' | cut -d'+' -f2 | cut -d'.' -f1)
    # AMD: Tdie
    elif sensors 2>/dev/null | grep -q "Tdie"; then
        temp=$(sensors | grep "Tdie" | awk '{print $2}' | cut -d'+' -f2 | cut -d'.' -f1)
    # Fallback: thermal_zone
    else
        temp=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null)
        temp=$((temp/1000))
    fi
    echo "${temp:-0}"
}

while true; do
    temp=$(get_cpu_temperature)

    if [[ $temp -ge $TEMP_THRESHOLD ]] && [[ "$paused" == false ]]; then
        if pgrep -x "$QBITTORRENT_PROCESS" > /dev/null; then
            pkill -STOP "$QBITTORRENT_PROCESS"
            paused=true
            pause_start=$(date +%s)
            log_message "PAUSED qBittorrent — CPU temp: ${temp}C (threshold: ${TEMP_THRESHOLD}C)"
        fi
    elif [[ $temp -lt $((TEMP_THRESHOLD - 10)) ]] && [[ "$paused" == true ]]; then
        pkill -CONT "$QBITTORRENT_PROCESS"
        paused=false
        log_message "RESUMED qBittorrent — CPU temp: ${temp}C"
    fi

    # Force resume if paused too long
    if [[ "$paused" == true ]]; then
        now=$(date +%s)
        elapsed=$((now - pause_start))
        if [[ $elapsed -ge $MAX_PAUSE_TIME ]]; then
            pkill -CONT "$QBITTORRENT_PROCESS"
            paused=false
            log_message "FORCE RESUMED qBittorrent after ${elapsed}s pause — CPU temp: ${temp}C"
        fi
    fi

    sleep $CHECK_INTERVAL
done
