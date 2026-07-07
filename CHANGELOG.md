# Changelog

## 2026-07-07
- Hardened `qbittorrent-temp-controller.sh`: use `pkill -x` so STOP/CONT/force-CONT only
  target the exact `qbittorrent-nox` process, not any process whose name merely contains it.
- `magnet_handler.py` now catches `FileNotFoundError` and notifies instead of crashing when
  the qBittorrent GUI binary is missing.
- Documented in README: `plex-watchdog.service` requires a self-supplied `plex_watchdog.sh`
  (not shipped in this repo), and `magnet_handler.py` requires qBittorrent's localhost
  auth-bypass setting to function.
- Fixed README troubleshooting pointer for qbittorrent-temp-control logs
  (`journalctl` -> `/var/log/qbittorrent-temp.log`).
