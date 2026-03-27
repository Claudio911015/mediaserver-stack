# Mediaserver Stack - Complete Infrastructure Guide

A self-hosted media server infrastructure distributed across three machines on a local network. Automates movie, TV series, and music acquisition, organization, and streaming via Plex, with supporting automation for DNS filtering, VPN privacy, daily briefings, and cloud sync.

---

## Quick Start

```bash
git clone https://github.com/YOUR_USER/mediaserver-stack.git
cd mediaserver-stack
cp .env.example .env
# Edit .env with your credentials (see "Environment Variables" section)
# Then:
cd thinkcentre/
docker compose -f docker-compose.yml up -d
# Complete initial setup wizards for each *arr app (see Step 3)
# Update .env with generated API keys
docker compose -f docker-compose-addons.yml up -d
```

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Machine Roles](#machine-roles)
3. [Data Flow](#data-flow)
4. [Service Interaction Map](#service-interaction-map)
5. [Environment Variables](#environment-variables)
6. [Docker Compose — Main Stack](#docker-compose--main-stack)
7. [Docker Compose — Addons Stack](#docker-compose--addons-stack)
8. [Configuration Files](#configuration-files)
9. [Watchdog Script](#watchdog-script)
10. [Deployment Guide](#deployment-guide)
11. [Post-Deployment Verification](#post-deployment-verification)
12. [Raspberry Pi Setup](#raspberry-pi-setup)
13. [Desktop Workstation (CLAU)](#desktop-workstation-clau)
14. [Volume Mounts & Hardlinks](#volume-mounts--hardlinks)
15. [Firewall (UFW)](#firewall-ufw)
16. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
17. [Backup & Restore](#backup--restore)
18. [Resource Usage](#resource-usage)
19. [Migration Status](#migration-status)

---

## Architecture Overview

```
                         ┌─────────────────────────────────────┐
                         │            INTERNET                 │
                         └──────┬──────────────┬───────────────┘
                                │              │
                         ┌──────▼──────┐ ┌─────▼──────────┐
                         │  Plex Relay  │ │  NordVPN       │
                         │  (port 32400)│ │  (NordLynx)    │
                         └──────┬──────┘ └─────┬──────────┘
                                │              │
       ┌────────────────────────┼──────────────┼────────────────────────┐
       │                   LOCAL NETWORK (LAN_SUBNET)                   │
       │                                                                │
       │  ┌─────────────────────────────────────────────────────────┐  │
       │  │         THINKCENTRE M700 (Media Server)                 │  │
       │  │                                                         │  │
       │  │  ┌─────────────────────────────────────────────────┐   │  │
       │  │  │           Docker — Main Stack                    │   │  │
       │  │  │                                                  │   │  │
       │  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │  │
       │  │  │  │  Plex   │  │ Radarr  │  │ Sonarr  │        │   │  │
       │  │  │  │ :32400  │  │ :7878   │  │ :8989   │        │   │  │
       │  │  │  └────┬────┘  └────┬────┘  └────┬────┘        │   │  │
       │  │  │       │            │             │              │   │  │
       │  │  │  ┌────┴────┐  ┌───┴─────┐  ┌───┴─────┐       │   │  │
       │  │  │  │ Lidarr  │  │Prowlarr │  │ Bazarr  │       │   │  │
       │  │  │  │ :8686   │  │ :9696   │  │ :6767   │       │   │  │
       │  │  │  └─────────┘  └────┬────┘  └─────────┘       │   │  │
       │  │  │                    │                           │   │  │
       │  │  │               ┌────┴─────────┐                │   │  │
       │  │  │               │ FlareSolverr  │                │   │  │
       │  │  │               │    :8191      │                │   │  │
       │  │  │               └──────────────┘                │   │  │
       │  │  └─────────────────────────────────────────────────┘   │  │
       │  │                                                         │  │
       │  │  ┌─────────────────────────────────────────────────┐   │  │
       │  │  │           Docker — Addons Stack                  │   │  │
       │  │  │                                                  │   │  │
       │  │  │  ┌──────────┐  ┌──────────────┐  ┌───────────┐ │   │  │
       │  │  │  │ Tautulli │  │  Decluttarr  │  │ Unpackerr │ │   │  │
       │  │  │  │  :8181   │  │  (headless)  │  │ (headless)│ │   │  │
       │  │  │  └──────────┘  └──────────────┘  └───────────┘ │   │  │
       │  │  │  ┌──────────┐  ┌──────────────┐                │   │  │
       │  │  │  │  Lidify  │  │    Kometa    │                │   │  │
       │  │  │  │  :5055   │  │  (daily 3am) │                │   │  │
       │  │  │  └──────────┘  └──────────────┘                │   │  │
       │  │  └─────────────────────────────────────────────────┘   │  │
       │  │                                                         │  │
       │  │  ┌──────────────────────────────┐                      │  │
       │  │  │  Host Services (systemd)     │                      │  │
       │  │  │  ├─ qBittorrent-nox (:8080)  │                      │  │
       │  │  │  │  └─ P2P: port 35902       │                      │  │
       │  │  │  ├─ arr-watchdog (60s loop)  │                      │  │
       │  │  │  ├─ plex-watchdog (60s loop) │                      │  │
       │  │  │  ├─ qbit-temp-control (10s)  │                      │  │
       │  │  │  ├─ Samba (SMB shares)       │                      │  │
       │  │  │  └─ Beets (CLI, on-demand)   │                      │  │
       │  │  └──────────────────────────────┘                      │  │
       │  │                                                         │  │
       │  │  ┌──────────────────────────────┐                      │  │
       │  │  │  Storage                     │                      │  │
       │  │  │  Disk 1 (~4 TB) — media      │                      │  │
       │  │  │  Disk 2 (~2 TB) — transcode  │                      │  │
       │  │  └──────────────────────────────┘                      │  │
       │  └─────────────────────────────────────────────────────────┘  │
       │                                                                │
       │  ┌─────────────────────────────────────────────────────────┐  │
       │  │         RASPBERRY PI 4 (DNS + VPN + Automation)         │  │
       │  │                                                         │  │
       │  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐ │  │
       │  │  │ Pi-hole  │  │   NordVPN    │  │  Cron: briefing  │ │  │
       │  │  │  (DNS)   │  │  (NordLynx)  │  │  6am daily       │ │  │
       │  │  │  :80     │  │  + watchdog  │  │  + cloud sync    │ │  │
       │  │  └──────────┘  └──────────────┘  └──────────────────┘ │  │
       │  │  ┌──────────────────┐  ┌────────────────────────────┐ │  │
       │  │  │  Telegram Bot    │  │  Google Drive + iCloud      │ │  │
       │  │  │  (remote cmds)   │  │  Sync (Obsidian vault)     │ │  │
       │  │  └──────────────────┘  └────────────────────────────┘ │  │
       │  └─────────────────────────────────────────────────────────┘  │
       │                                                                │
       │  ┌─────────────────────────────────────────────────────────┐  │
       │  │         CLAU (Desktop Workstation)                      │  │
       │  │                                                         │  │
       │  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  │  │
       │  │  │ Plex (legacy │  │  Nicotine+  │  │  Tailscale   │  │  │
       │  │  │  migrating)  │  │  (Soulseek) │  │  (remote)    │  │  │
       │  │  └──────────────┘  └─────────────┘  └──────────────┘  │  │
       │  │  ┌──────────────┐  ┌──────────────────────────────┐   │  │
       │  │  │  NordVPN     │  │  Magnet handler + KAT scraper│   │  │
       │  │  │  + watchdog  │  │  (torrent automation)        │   │  │
       │  │  └──────────────┘  └──────────────────────────────┘   │  │
       │  └─────────────────────────────────────────────────────────┘  │
       └────────────────────────────────────────────────────────────────┘
```

---

## Machine Roles

### ThinkCentre M700 — Media Server

| Property | Value |
|---|---|
| Role | Primary media server: runs all Docker workloads, downloads, Plex |
| OS | Ubuntu 24.04 LTS |
| IP | Static LAN IP (set in `.env` as `SERVER_IP`) |
| Storage | Disk 1 (~4 TB, primary media), Disk 2 (~2 TB, Plex transcode temp) |
| RAM | 8 GB minimum recommended (16 GB for concurrent transcoding + Kometa) |

### Raspberry Pi 4 — DNS + VPN + Automation

| Property | Value |
|---|---|
| Role | Network-wide DNS filtering, VPN privacy, daily briefing, cloud sync |
| OS | Raspberry Pi OS (Debian-based) |
| IP | Static IP on eth0 (WiFi disabled for reliability) |
| Connection | Wired Ethernet only |

### CLAU — Desktop Workstation

| Property | Value |
|---|---|
| Role | Desktop, legacy Plex (migrating), Soulseek music sharing, torrent automation |
| OS | Linux (Ubuntu/Debian-based), KDE Plasma 6 |
| Special | Performance-tuned: 13 KWin effects disabled, CPU governor `performance`, plasmashell auto-restart every 3 days (Plasma 6 memory leak mitigation) |

---

## Data Flow

### Torrent Search & Download Flow

```
User search → Prowlarr (14 indexers: 1337x, TPB, RuTracker, Knaben, etc.)
                    │
                    │ pushes results to the requesting *arr app
                    │
        ┌───────────┼───────────────┐
        ▼           ▼               ▼
     Radarr      Sonarr          Lidarr
    (movies)    (series)        (music)
        │           │               │
        │           │               ├──→ Tubifarry plugin (YouTube DL)
        │           │               │    (alternative download source)
        └─────┬─────┘               │
              ▼                     ▼
         qBittorrent ◄──────────────┘
         (systemd, port 35902 for P2P)
              │
              ▼
         Unpackerr
         (extracts RAR archives if present)
              │
              │ notifies the originating *arr app
              │
        ┌─────┼─────────┐
        ▼     ▼         ▼
     Radarr Sonarr   Lidarr   ← import completed files
        │     │         │
        ▼     ▼         ▼
     Primary Disk (single mount point)
     ├── /peliculas/     (movies)
     ├── /series/        (TV shows)
     └── /musica/        (music, ~1400 artists)
              │
              ▼
      Plex Media Server
      (auto-scans on *arr notification)
              │
      ┌───────┼───────┐
      ▼       ▼       ▼
   Kometa  Tautulli  Bazarr
  (overlays) (stats) (subtitles)
```

**Key detail:** qBittorrent runs as a native systemd service, not in Docker. Docker containers (Decluttarr, Unpackerr, the *arr apps) communicate with it via the host IP on port 8080. This works because the addons Docker network has UFW rules allowing it to reach host ports.

### Music Discovery Flow

```
Last.fm scrobbles → Lidify → discovers similar artists → Lidarr → qBittorrent
                                                            │
                                                            ▼
Beets (CLI, manual) → tags/organizes music on disk → notifies Plex (plexupdate plugin)
```

### Queue Maintenance Flow

```
Decluttarr (runs continuously every ~2 min)
    │
    ├── Queries Radarr/Sonarr/Lidarr download queues via their APIs
    ├── Identifies: stalled torrents, stuck metadata, missing files, orphans
    ├── Removes problematic entries from *arr queues
    └── Deletes corresponding torrents from qBittorrent
```

### DNS + Privacy Flow

```
All LAN devices ──DNS──→ Pi-hole (blocks ads/trackers) ──→ upstream DNS
Raspberry Pi ──────────→ NordVPN tunnel (NordLynx/WireGuard)
CLAU desktop ──────────→ NordVPN + Tailscale (VPN + remote access)
```

---

## Service Interaction Map

| Service | Talks to | Protocol/Method |
|---|---|---|
| **Prowlarr** | Radarr, Sonarr, Lidarr (pushes indexer configs) | HTTP API |
| | FlareSolverr (Cloudflare bypass) | HTTP on shared bridge network |
| **Radarr** | Prowlarr (indexers), qBittorrent (downloads), Plex (notifications) | HTTP API |
| **Sonarr** | Prowlarr (indexers), qBittorrent (downloads), Plex (notifications) | HTTP API |
| **Lidarr** | Prowlarr (indexers), qBittorrent (downloads), Plex (notifications) | HTTP API |
| | Tubifarry plugin → YouTube (alternative music downloads) | HTTPS |
| **Bazarr** | Radarr + Sonarr (reads movie/series lists), subtitle providers | HTTP API + HTTPS |
| **Decluttarr** | Radarr, Sonarr, Lidarr (reads queues), qBittorrent (deletes bad torrents) | HTTP API via host IP |
| **Unpackerr** | Radarr, Sonarr, Lidarr (monitors download paths, notifies on extraction) | HTTP API |
| **Tautulli** | Plex (reads play history, active streams) | HTTP API |
| **Kometa** | Plex (creates collections, applies resolution overlays), TMDB API (metadata) | HTTP API + HTTPS |
| **Lidify** | Last.fm API (discovers similar artists), Lidarr (adds artists) | HTTPS + HTTP API |
| **Beets** | MusicBrainz (tagging), Last.fm (genres, scrobbles), Plex (library refresh) | HTTPS + HTTP API |
| **arr-watchdog** | All Docker containers (health check via HTTP or container state) | Docker API + HTTP |
| **Pi-hole** | All LAN devices (DNS resolver) | DNS (port 53) |
| **NordVPN watchdog** | NordVPN daemon, Telegram API (alerts) | CLI + HTTPS |
| **Magnet handler (CLAU)** | qBittorrent on ThinkCentre (sends categorized magnet links) | HTTP API |

---

## Environment Variables

Create a `.env` file in the same directory as the Docker Compose files (`/opt/mediaserver/` or your chosen deployment directory).

A `.env.example` is provided in the repository:

```bash
# ─── Timezone ─────────────────────────────────────────────
TZ=America/Mexico_City

# ─── Host ─────────────────────────────────────────────────
SERVER_IP=your_server_lan_ip        # e.g., 192.168.1.100
LAN_SUBNET=your_lan_subnet/mask    # e.g., 192.168.1.0/24
PUID=1000
PGID=1000

# ─── Storage Paths ────────────────────────────────────────
MEDIA_DISK=/path/to/primary/disk    # e.g., /media/user/disk
SECONDARY_DISK=/path/to/second/disk # e.g., /media/user/disk2 (for Plex transcode)
MOVIES_DIR=${MEDIA_DISK}/peliculas
SERIES_DIR=${MEDIA_DISK}/series
MUSIC_DIR=${MEDIA_DISK}/musica
DOWNLOADS_DIR=${MEDIA_DISK}/peliculas/downloads

# ─── Plex ─────────────────────────────────────────────────
PLEX_CLAIM=your_plex_claim_token    # Get from https://plex.tv/claim (4 min expiry)
PLEX_TOKEN=your_plex_token          # Get from Plex WebUI → XML trick or PlexAPI

# ─── *arr API Keys (generated on first run) ───────────────
RADARR_API_KEY=your_radarr_api_key
SONARR_API_KEY=your_sonarr_api_key
LIDARR_API_KEY=your_lidarr_api_key
PROWLARR_API_KEY=your_prowlarr_api_key

# ─── qBittorrent ──────────────────────────────────────────
QBIT_PORT=8080
QBIT_P2P_PORT=35902
QBIT_USERNAME=your_qbit_username
QBIT_PASSWORD=your_qbit_password

# ─── TMDB (for Kometa) ───────────────────────────────────
TMDB_API_KEY=your_tmdb_api_key      # Get from https://www.themoviedb.org/settings/api

# ─── Last.fm (for Lidify + Beets) ────────────────────────
LASTFM_API_KEY=your_lastfm_api_key
LASTFM_USERNAME=your_lastfm_username

# ─── Telegram (optional, for Pi notifications) ───────────
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# ─── NordVPN (optional, for Raspberry Pi) ────────────────
NORDVPN_TOKEN=your_nordvpn_token

# ─── Docker Networks ─────────────────────────────────────
# These are internal Docker subnets. Change only if they
# conflict with your existing networks.
ADDONS_SUBNET=172.19.0.0/16
ADDONS_GATEWAY=172.19.0.1
```

---

## Docker Compose — Main Stack

File: `docker-compose.yml`

This stack contains Plex and the core *arr applications. Plex uses `network_mode: host` because it needs UPnP/DLNA discovery and direct play on the LAN.

The *arr apps, Bazarr, and FlareSolverr use port-mapped bridge networking.

```yaml
networks:
  medianet:
    name: medianet
    driver: bridge

services:

  plex:
    image: plexinc/pms-docker:latest
    container_name: plex
    network_mode: host
    environment:
      - TZ=${TZ}
      - PLEX_CLAIM=${PLEX_CLAIM}
      - PLEX_UID=${PUID}
      - PLEX_GID=${PGID}
    volumes:
      - /opt/mediaserver/config/plex:/config
      - /opt/mediaserver/config/plex/transcode:/transcode
      - ${MEDIA_DISK}:${MEDIA_DISK}:ro
      - ${SECONDARY_DISK}:${SECONDARY_DISK}:ro
    devices:
      - /dev/dri:/dev/dri    # Intel QuickSync hardware transcoding
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:32400/identity"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: radarr
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ}
    volumes:
      - /opt/mediaserver/config/radarr:/config
      - ${MEDIA_DISK}:${MEDIA_DISK}
    ports:
      - 7878:7878
    networks:
      - medianet
    restart: unless-stopped

  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
    container_name: sonarr
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ}
    volumes:
      - /opt/mediaserver/config/sonarr:/config
      - ${MEDIA_DISK}:${MEDIA_DISK}
    ports:
      - 8989:8989
    networks:
      - medianet
    restart: unless-stopped

  lidarr:
    image: lscr.io/linuxserver/lidarr:nightly
    # IMPORTANT: nightly is required for plugin support (Tubifarry).
    # Stable Lidarr (lidarr:latest) has no plugin system.
    container_name: lidarr
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ}
    volumes:
      - /opt/mediaserver/config/lidarr:/config
      - ${MEDIA_DISK}:${MEDIA_DISK}
    ports:
      - 8686:8686
    networks:
      - medianet
    restart: unless-stopped

  prowlarr:
    image: lscr.io/linuxserver/prowlarr:latest
    container_name: prowlarr
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ}
    volumes:
      - /opt/mediaserver/config/prowlarr:/config
    ports:
      - 9696:9696
    networks:
      - medianet
    restart: unless-stopped

  bazarr:
    image: lscr.io/linuxserver/bazarr:latest
    container_name: bazarr
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ}
    volumes:
      - /opt/mediaserver/config/bazarr:/config
      - ${MEDIA_DISK}:${MEDIA_DISK}
    ports:
      - 6767:6767
    networks:
      - medianet
    restart: unless-stopped

  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    environment:
      - TZ=${TZ}
    ports:
      - 8191:8191
    networks:
      - medianet
    restart: unless-stopped
```

---

## Docker Compose — Addons Stack

File: `docker-compose-addons.yml`

These containers live on a separate Docker network (`addonsnet`). They communicate with host services (qBittorrent, Plex, *arr apps) via the Docker gateway IP or the server's LAN IP.

**Why a separate network?** Isolation. The addons don't need to talk to each other, only to host services. Keeping them separate makes firewall rules cleaner and prevents accidental cross-contamination.

```yaml
networks:
  addonsnet:
    name: addonsnet
    driver: bridge
    ipam:
      config:
        - subnet: ${ADDONS_SUBNET}
          gateway: ${ADDONS_GATEWAY}

services:

  tautulli:
    image: lscr.io/linuxserver/tautulli:latest
    container_name: tautulli
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ}
    volumes:
      - /opt/mediaserver/config/tautulli:/config
    ports:
      - 8181:8181
    networks:
      - addonsnet
    restart: unless-stopped

  decluttarr:
    image: ghcr.io/manimatter/decluttarr:latest
    container_name: decluttarr
    environment:
      - TZ=${TZ}
      - LOG_LEVEL=INFO
      - TEST_RUN=False
      # --- Radarr ---
      - RADARR_URL=http://${SERVER_IP}:7878
      - RADARR_KEY=${RADARR_API_KEY}
      # --- Sonarr ---
      - SONARR_URL=http://${SERVER_IP}:8989
      - SONARR_KEY=${SONARR_API_KEY}
      # --- Lidarr ---
      - LIDARR_URL=http://${SERVER_IP}:8686
      - LIDARR_KEY=${LIDARR_API_KEY}
      # --- qBittorrent ---
      - QBITTORRENT_URL=http://${SERVER_IP}:${QBIT_PORT}
      - QBITTORRENT_USERNAME=${QBIT_USERNAME}
      - QBITTORRENT_PASSWORD=${QBIT_PASSWORD}
      # --- Cleanup rules ---
      - REMOVE_STALLED=True
      - REMOVE_METADATA_MISSING=True
      - REMOVE_MISSING_FILES=True
      - REMOVE_NO_FORMAT_UPGRADE=False
      - REMOVE_ORPHANS=True
      - MIN_DOWNLOAD_SPEED=100        # kB/s — below this = stalled
      - PERMITTED_ATTEMPTS=3          # retries before removal
      - NO_STALLED_REMOVAL_QBIT_TAG=Don't Kill   # tag to protect torrents
    networks:
      - addonsnet
    restart: unless-stopped

  unpackerr:
    image: golift/unpackerr:latest
    container_name: unpackerr
    user: "${PUID}:${PGID}"
    environment:
      - TZ=${TZ}
    volumes:
      - /opt/mediaserver/config/unpackerr/unpackerr.conf:/etc/unpackerr/unpackerr.conf:ro
      - ${MEDIA_DISK}:${MEDIA_DISK}
    networks:
      - addonsnet
    restart: unless-stopped

  lidify:
    image: thewicklowwolf/lidify:latest
    container_name: lidify
    environment:
      - TZ=${TZ}
      - lidarr_address=http://${SERVER_IP}:8686
      - lidarr_api_key=${LIDARR_API_KEY}
      - last_fm_api_key=${LASTFM_API_KEY}
      - lastfm_username=${LASTFM_USERNAME}
      - number_of_artists=10
      - search_for_missing_albums=True
      - thread_limit=1
    volumes:
      - /opt/mediaserver/config/lidify:/lidify/config
    ports:
      - 5055:5000
    networks:
      - addonsnet
    restart: unless-stopped

  kometa:
    image: kometateam/kometa:latest
    container_name: kometa
    environment:
      - TZ=${TZ}
      - KOMETA_CONFIG=/config/config.yml
      - KOMETA_TIME=03:00             # daily run at 3 AM
      - KOMETA_RUN=false              # set to true to trigger immediate run
    volumes:
      - /opt/mediaserver/config/kometa:/config
    networks:
      - addonsnet
    restart: unless-stopped
```

---

## Configuration Files

### Kometa — `config/kometa/config.yml`

Kometa (formerly Plex Meta Manager) applies collections and resolution overlays to Plex libraries.

```yaml
plex:
  url: http://${SERVER_IP}:32400
  token: ${PLEX_TOKEN}
  timeout: 60
  clean_bundles: false
  empty_trash: false
  optimize: false

tmdb:
  apikey: ${TMDB_API_KEY}
  language: es               # change to your language
  cache_expiration: 60

settings:
  cache: true
  cache_expiration: 60
  asset_directory: config/assets
  asset_folders: true
  sync_mode: append
  minimum_items: 1
  delete_below_minimum: true
  run_order:
    - operations
    - metadata
    - collections
    - overlays
  overlay_artwork_filetype: webp_lossy
  overlay_artwork_quality: 90

libraries:
  Movies:
    collection_files:
      - default: basic         # "Recently Added", "Top Rated", etc.
      - default: imdb          # IMDB Top 250
      - default: trakt         # Trakt popular/trending
    overlay_files:
      - default: resolution    # 4K, 1080p, 720p badges on posters
      - default: audio_codec   # Atmos, DTS-HD badges
  Series:
    collection_files:
      - default: basic
      - default: imdb
  Music:
    collection_files:
      - default: basic
```

**Replace** `${SERVER_IP}`, `${PLEX_TOKEN}`, and `${TMDB_API_KEY}` with actual values (Kometa does not read Docker `.env` files; its config is standalone YAML).

### Unpackerr — `config/unpackerr/unpackerr.conf`

Monitors *arr download paths and extracts RAR archives automatically.

```toml
debug = false
quiet = false
interval = "2m"
start_delay = "1m"
retry_delay = "5m"
max_retries = 3
parallel = 1
file_mode = "0644"
dir_mode = "0755"

[[radarr]]
url = "http://SERVER_IP:7878"
api_key = "RADARR_API_KEY"
paths = ["/path/to/media/peliculas"]
protocols = "torrent"
timeout = "10s"
delete_delay = "5m"
delete_orig = false

[[sonarr]]
url = "http://SERVER_IP:8989"
api_key = "SONARR_API_KEY"
paths = ["/path/to/media/series"]
protocols = "torrent"
timeout = "10s"
delete_delay = "5m"
delete_orig = false

[[lidarr]]
url = "http://SERVER_IP:8686"
api_key = "LIDARR_API_KEY"
paths = ["/path/to/media/musica"]
protocols = "torrent"
timeout = "10s"
delete_delay = "5m"
delete_orig = false
```

**Replace** all `SERVER_IP`, `*_API_KEY`, and paths with your actual values. Unpackerr reads TOML directly, not Docker env vars.

### Lidify — `config/lidify/settings_config.json`

Auto-generated on first launch. Key fields to modify:

```json
{
    "lidarr_address": "http://SERVER_IP:8686",
    "lidarr_api_key": "LIDARR_API_KEY",
    "root_folder_path": "/path/to/media/musica/",
    "mode": "Last.fm",
    "last_fm_api_key": "LASTFM_API_KEY",
    "auto_start": true,
    "auto_start_delay": 30,
    "quality_profile_id": 1,
    "metadata_profile_id": 1,
    "search_for_missing_albums": true,
    "dry_run_adding_to_lidarr": false
}
```

**Note:** Lidify writes this file on first start with defaults. Stop the container, edit the file, then restart.

### Beets — `~/.config/beets/config.yaml`

Installed natively (not Docker). Run on the ThinkCentre host.

```yaml
directory: /path/to/media/musica
library: ~/.config/beets/library.db

plugins:
  - fetchart      # downloads album art
  - embedart      # embeds art into audio files
  - lastgenre     # genre tags from Last.fm
  - lastimport    # imports Last.fm scrobble counts
  - mbsync        # syncs MusicBrainz metadata updates
  - edit          # opens tags in $EDITOR
  - duplicates    # finds duplicate tracks
  - missing       # finds missing tracks in albums
  - info          # displays tag info
  - scrub         # removes non-standard tags
  - plexupdate    # notifies Plex to rescan after import

import:
  move: no                 # tag in-place, do not move files
  copy: no
  write: yes               # write tags to audio files
  autotag: yes
  incremental: yes         # skip already-imported items
  incremental_skip_later: yes
  quiet: yes               # batch mode, no interactive prompts
  resume: yes
  log: ~/.config/beets/import.log

match:
  strong_rec_thresh: 0.05
  medium_rec_thresh: 0.20
  distance_weights:
    album: 1.0
    artist: 1.0
    totaltracks: 0.4
    missing_tracks: 0.4
    unmatched_tracks: 0.4
    year: 0.1

fetchart:
  auto: yes
  sources: [filesystem, coverart, itunes, lastfm, wikipedia]
  minwidth: 300
  enforce_ratio: no

embedart:
  auto: yes
  maxwidth: 500

lastgenre:
  auto: yes
  source: album
  count: 3
  separator: ", "
  canonical: yes
  api_key: LASTFM_API_KEY       # replace with your Last.fm API key

lastimport:
  username: LASTFM_USERNAME     # replace with your Last.fm username
  api_key: LASTFM_API_KEY       # replace with your Last.fm API key

plexupdate:
  host: SERVER_IP               # replace with your server IP
  port: 32400
  token: PLEX_TOKEN             # replace with your Plex token
```

**Common Beets commands:**

```bash
# Import entire music library (first run, takes hours for large libraries)
beet import /path/to/media/musica

# Import a single album
beet import /path/to/media/musica/Artist/Album

# Preview matches without writing (timid mode)
beet import -t /path/to/media/musica/Artist/Album

# List missing tracks
beet missing

# Find duplicates
beet duplicates

# Update tags from MusicBrainz
beet mbsync

# Import Last.fm scrobble counts
beet lastimport
```

---

## Watchdog Script

File: `scripts/arr_watchdog.sh`

The watchdog monitors all Docker containers every 60 seconds. For containers with a web interface, it performs an HTTP health check. For headless containers (no web UI), it only checks that the Docker container state is "running."

If a container is unresponsive to HTTP but running, it restarts it. If a container is not running at all, it starts it.

```bash
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
```

**Systemd unit** (`/etc/systemd/system/arr-watchdog.service`):

```ini
[Unit]
Description=ARR Stack Watchdog
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/local/bin/arr_watchdog.sh start
Restart=always
RestartSec=30
User=root
StandardOutput=append:/var/log/arr_watchdog.log
StandardError=append:/var/log/arr_watchdog.log

[Install]
WantedBy=multi-user.target
```

---

## Deployment Guide

### Prerequisites

- Ubuntu 22.04+ server with Docker Engine + Docker Compose V2
- At least 2 storage disks (recommended: ~4 TB primary, ~2 TB secondary)
- Open ports: 32400/tcp (Plex), 35902/tcp+udp (qBittorrent P2P)
- A Plex account (Plex Pass recommended for hardware transcoding)
- Optional: Raspberry Pi 4 for DNS/VPN, desktop Linux for CLAU role

### Step 1: Prepare the Server

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group to take effect

# Create directory structure
sudo mkdir -p /opt/mediaserver/config/{plex,plex/transcode,radarr,sonarr,lidarr,prowlarr,bazarr,tautulli,kometa,unpackerr,lidify}
sudo chown -R $(id -u):$(id -g) /opt/mediaserver

# Mount your storage disks (add to /etc/fstab for persistence)
# Ensure both are mounted at consistent paths
```

### Step 2: Install qBittorrent (Host Service)

qBittorrent runs outside Docker for direct disk access and better P2P performance.

```bash
sudo apt install qbittorrent-nox

# Create systemd service
sudo tee /etc/systemd/system/qbittorrent-nox@.service << 'EOF'
[Unit]
Description=qBittorrent-nox service for user %i
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=%i
ExecStart=/usr/bin/qbittorrent-nox --webui-port=8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now qbittorrent-nox@$(whoami)

# First-run: access WebUI at http://SERVER_IP:8080
# Default credentials are printed in journalctl
# Change username/password immediately
# Set download paths for each category:
#   Movies → ${MEDIA_DISK}/peliculas/downloads
#   Series → ${MEDIA_DISK}/series/downloads
#   Music  → ${MEDIA_DISK}/musica/downloads
# Set P2P listening port to 35902
```

### Step 3: Deploy Main Stack & Configure *arr Apps

```bash
cd /opt/mediaserver
cp .env.example .env
# Edit .env: set SERVER_IP, disk paths, PLEX_CLAIM, PUID/PGID, TZ

docker compose -f docker-compose.yml up -d
```

Wait for all containers to start, then configure each via WebUI:

1. **Radarr** (`http://SERVER_IP:7878`)
   - Settings → Media Management → Root Folder: `${MEDIA_DISK}/peliculas`
   - Settings → Download Clients → Add qBittorrent: host=`SERVER_IP`, port=`8080`, username/password
   - Settings → General → Note the API Key

2. **Sonarr** (`http://SERVER_IP:8989`)
   - Same as Radarr but root folder: `${MEDIA_DISK}/series`
   - Note the API Key

3. **Lidarr** (`http://SERVER_IP:8686`)
   - Same as Radarr but root folder: `${MEDIA_DISK}/musica`
   - Note the API Key

4. **Prowlarr** (`http://SERVER_IP:9696`)
   - Settings → Apps → Add Radarr, Sonarr, Lidarr (use their API keys and `SERVER_IP`)
   - Indexers → Add your preferred torrent indexers
   - Settings → FlareSolverr → URL: `http://SERVER_IP:8191` (for Cloudflare-protected indexers)

5. **Bazarr** (`http://SERVER_IP:6767`)
   - Settings → Radarr → URL: `http://SERVER_IP:7878`, API Key
   - Settings → Sonarr → URL: `http://SERVER_IP:8989`, API Key
   - Settings → Providers → Add subtitle providers (OpenSubtitles, Subdivx, etc.)

**Update `.env`** with the API keys you noted from each app.

### Step 4: Deploy Addons Stack

```bash
# Write config files first (see "Configuration Files" section above)
# Replace all placeholders with actual values

docker compose -f docker-compose-addons.yml up -d
```

### Step 5: Install Lidarr Tubifarry Plugin

```bash
# Lidarr must be running the nightly image (already set in compose)
curl -s -X POST "http://${SERVER_IP}:8686/api/v1/command" \
  -H "X-Api-Key: ${LIDARR_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"name":"InstallPlugin","gitHubUrl":"https://github.com/TypNull/Tubifarry","branch":"main"}'

# Restart Lidarr to load the plugin
docker restart lidarr

# In Lidarr WebUI → Settings → Download Clients → Add "YouTube (Tubifarry)"
```

### Step 6: Install Beets

```bash
pip install beets pylast
mkdir -p ~/.config/beets
# Copy the beets config from "Configuration Files" section
# Replace all placeholders with actual values
nano ~/.config/beets/config.yaml

# Verify plugins loaded
beet version
# Should show: plugins: duplicates, edit, embedart, fetchart, ...
```

### Step 7: Install Watchdog

```bash
sudo cp scripts/arr_watchdog.sh /usr/local/bin/arr_watchdog.sh
sudo chmod +x /usr/local/bin/arr_watchdog.sh
sudo cp systemd/arr-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now arr-watchdog
```

### Step 8: Configure Firewall

See [Firewall (UFW)](#firewall-ufw) section below.

---

## Post-Deployment Verification

Run through this checklist after deployment:

| Check | Command / URL | Expected |
|---|---|---|
| Plex WebUI loads | `http://SERVER_IP:32400/web` | Plex dashboard, claim server if first run |
| Radarr WebUI loads | `http://SERVER_IP:7878` | Radarr UI with root folder configured |
| Sonarr WebUI loads | `http://SERVER_IP:8989` | Sonarr UI with root folder configured |
| Lidarr WebUI loads | `http://SERVER_IP:8686` | Lidarr UI, check Tubifarry in plugins |
| Prowlarr has indexers | `http://SERVER_IP:9696` | Indexers configured, apps connected |
| Bazarr connected | `http://SERVER_IP:6767` | Radarr + Sonarr integration green |
| qBittorrent WebUI | `http://SERVER_IP:8080` | Login works, categories set |
| Tautulli connected to Plex | `http://SERVER_IP:8181` | Shows Plex server info |
| Lidify in Last.fm mode | `http://SERVER_IP:5055` | Mode shows "Last.fm", Lidarr connected |
| Watchdog all green | `arr_watchdog.sh status` | All containers: `running` |
| P2P port open | Test at canyouseeme.org for port 35902 | Port reachable |
| Plex remote access | Plex Settings → Remote Access | Green checkmark or relay active |
| Test download | Add a movie in Radarr → search | Downloads start in qBittorrent |
| Beets loaded | `beet version` | Shows all plugins |

---

## Raspberry Pi Setup

### Pi-hole (DNS Ad Blocking)

```bash
# Install Pi-hole
curl -sSL https://install.pi-hole.net | bash
# Follow the interactive installer
# Set your router's DNS to the Pi's IP address

# Access: http://PI_IP/admin
# Set admin password: pihole -a -p YOUR_PASSWORD
```

### NordVPN

```bash
# Install NordVPN
sh <(curl -sSf https://downloads.nordcdn.com/apps/linux/install.sh)

# Login with token
nordvpn login --token YOUR_NORDVPN_TOKEN

# Configure
nordvpn set technology nordlynx     # WireGuard-based, fastest
nordvpn set killswitch off          # allow LAN access if VPN drops
nordvpn whitelist add subnet LAN_SUBNET   # e.g., 192.168.1.0/24

# Connect
nordvpn connect
```

### NordVPN Watchdog

File: `scripts/nordvpn-watchdog.sh`

Checks VPN connection every 30 seconds. If disconnected, attempts reconnection up to 3 times. Sends Telegram notifications on state changes. Falls back to retry every 15 minutes if reconnection keeps failing.

```bash
#!/bin/bash
# nordvpn-watchdog.sh — Keeps NordVPN connected with auto-reconnect

TELEGRAM_TOKEN="${TELEGRAM_BOT_TOKEN}"   # replace with your bot token
CHAT_ID="${TELEGRAM_CHAT_ID}"            # replace with your chat ID
LOG="/var/log/nordvpn-watchdog.log"
MAX_RETRIES=3
RETRY_INTERVAL=30
CHECK_INTERVAL=30
FALLBACK_RETRY=900   # 15 min

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

telegram() {
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        -d text="NordVPN Pi: ${1}" \
        -d parse_mode="Markdown" > /dev/null 2>&1
}

vpn_connected() { nordvpn status 2>/dev/null | grep -q "Status: Connected"; }

log "=== NordVPN Watchdog started ==="
while true; do
    if ! vpn_connected; then
        log "VPN disconnected — attempting reconnect..."
        telegram "VPN disconnected, reconnecting..."
        for i in $(seq 1 $MAX_RETRIES); do
            nordvpn connect && break
            sleep $RETRY_INTERVAL
        done
        if vpn_connected; then
            log "VPN reconnected successfully"
            telegram "VPN reconnected"
        else
            log "ERROR: could not reconnect after $MAX_RETRIES attempts. Retrying in ${FALLBACK_RETRY}s..."
            telegram "ERROR: VPN reconnection failed. Retrying in 15 min."
            sleep $FALLBACK_RETRY
        fi
    fi
    sleep $CHECK_INTERVAL
done
```

**Systemd unit** (`/etc/systemd/system/nordvpn-watchdog.service`):

```ini
[Unit]
Description=NordVPN Watchdog
After=network-online.target nordvpnd.service

[Service]
Type=simple
ExecStart=/usr/local/bin/nordvpn-watchdog.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Daily Briefing & Cloud Sync

The Pi generates a daily briefing at 6:00 AM (news, finance, weather), syncs it to an Obsidian vault, pushes to iCloud and Google Drive, and sends a Telegram notification.

**Cron jobs:**

```cron
# Daily briefing + sync
0 6 * * * /path/to/venv/bin/python /path/to/briefing_completo.py --cleanup 7 --audio-format brief && sleep 30 && /path/to/venv/bin/python /path/to/sync_notion.py

# Hourly Google Drive sync
0 * * * * /path/to/sync_google_drive.sh

# Nightly Google Drive sync
0 23 * * * /path/to/sync_google_drive.sh
```

### Telegram Bot

A Telegram bot (`telegram_bot_executor.py`) listens for commands and executes them on the Pi. Used for remote management (reboot, VPN status, trigger briefing, etc.).

```ini
# /etc/systemd/system/telegram-bot.service
[Unit]
Description=Telegram Bot Executor
After=network-online.target

[Service]
Type=simple
User=your_user
ExecStart=/path/to/venv/bin/python /path/to/telegram_bot_executor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Desktop Workstation (CLAU)

The desktop machine serves as the primary user interface and runs some services that haven't been migrated to the ThinkCentre yet.

### Active Services

| Service | Purpose |
|---|---|
| Plex (legacy) | Still running during migration. Will be deactivated once ThinkCentre Plex is fully verified. |
| Nicotine+ (Soulseek) | P2P music sharing. Shares music library with the Soulseek network. |
| NordVPN + watchdog | VPN for desktop privacy. Watchdog checks connection every 60s. |
| Tailscale | Mesh VPN for remote access to this machine from anywhere. |
| Magnet handler | Custom script that intercepts magnet links from the browser, auto-categorizes them (movies, series, music), and sends them to qBittorrent on the ThinkCentre. |
| KAT scraper | Python script that searches KickassTorrents and bulk-adds results to qBittorrent on the ThinkCentre. |

### Performance Optimizations

| Optimization | Details |
|---|---|
| KWin compositor | 13 effects disabled (blur, contrast, diminactive, shakecursor, mouseclick, colorpicker, slidingpopups, windowaperture, slide, fadingpopups, blendchanges, dialogparent, startupfeedback) |
| CPU governor | Set to `performance` mode |
| irqbalance | Active for interrupt distribution |
| plasmashell | Auto-restarts every 3 days at 4 AM via cron (mitigates Plasma 6 memory leak) |

---

## Volume Mounts & Hardlinks

### Why This Matters

The *arr apps (Radarr, Sonarr, Lidarr) can use **hardlinks** instead of copying files when the download directory and the library directory are on the same filesystem. This saves disk space and avoids slow file copies.

**Rule:** The download path and the root folder path must be on the **same physical disk partition** AND the Docker container must see them under the **same mount point**.

### Mount Structure

```
Host path                           Container path               Used by
─────────────────────────────────   ─────────────────────────    ──────────────
${MEDIA_DISK}                       ${MEDIA_DISK}                Radarr, Sonarr, Lidarr, Bazarr, Unpackerr
${MEDIA_DISK}/peliculas/            (same)                       Radarr root folder
${MEDIA_DISK}/peliculas/downloads/  (same)                       qBittorrent "Movies" category
${MEDIA_DISK}/series/               (same)                       Sonarr root folder
${MEDIA_DISK}/series/downloads/     (same)                       qBittorrent "Series" category
${MEDIA_DISK}/musica/               (same)                       Lidarr root folder
${SECONDARY_DISK}                   ${SECONDARY_DISK}            Plex (transcode temp)
```

**Key:** Both the Compose files and qBittorrent use identical absolute paths (`${MEDIA_DISK}/peliculas/downloads`). This ensures hardlinks work because the *arr app sees the same path as the download client.

---

## Firewall (UFW)

**Note about security:** Ports 32400 and 35902 are exposed to the internet for Plex remote access and qBittorrent P2P respectively. All other services are LAN-only. Ensure you use strong passwords for any internet-facing service.

```bash
# ── Public (WAN) ──────────────────────────────────
sudo ufw allow 32400/tcp      # Plex remote access
sudo ufw allow 35902/tcp      # qBittorrent P2P
sudo ufw allow 35902/udp      # qBittorrent P2P

# ── LAN access ────────────────────────────────────
# Replace LAN_SUBNET with your actual subnet (e.g., 192.168.1.0/24)
sudo ufw allow from ${LAN_SUBNET} to any port 22    # SSH
sudo ufw allow from ${LAN_SUBNET} to any port 8080  # qBittorrent WebUI
sudo ufw allow from ${LAN_SUBNET} to any port 7878  # Radarr
sudo ufw allow from ${LAN_SUBNET} to any port 8989  # Sonarr
sudo ufw allow from ${LAN_SUBNET} to any port 8686  # Lidarr
sudo ufw allow from ${LAN_SUBNET} to any port 9696  # Prowlarr
sudo ufw allow from ${LAN_SUBNET} to any port 6767  # Bazarr
sudo ufw allow from ${LAN_SUBNET} to any port 8181  # Tautulli
sudo ufw allow from ${LAN_SUBNET} to any port 8191  # FlareSolverr
sudo ufw allow from ${LAN_SUBNET} to any port 5055  # Lidify

# ── Docker → Host (addonsnet containers reaching host services) ──
# Get actual subnet: docker network inspect addonsnet | grep Subnet
sudo ufw allow from ${ADDONS_SUBNET} to any port 7878  # Radarr
sudo ufw allow from ${ADDONS_SUBNET} to any port 8989  # Sonarr
sudo ufw allow from ${ADDONS_SUBNET} to any port 8686  # Lidarr
sudo ufw allow from ${ADDONS_SUBNET} to any port 8080  # qBittorrent
sudo ufw allow from ${ADDONS_SUBNET} to any port 32400 # Plex

sudo ufw enable
```

---

## Monitoring & Troubleshooting

### Health Checks

```bash
# All containers at once
arr_watchdog.sh status

# Docker overview
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Watchdog logs (live)
tail -f /var/log/arr_watchdog.log

# Individual container logs
docker logs <container_name> --tail 50

# Kometa run logs (after nightly run)
docker logs kometa --tail 100
```

### Common Issues

| Issue | Cause | Solution |
|---|---|---|
| Container keeps restarting | Config error or port conflict | `docker logs <name> --tail 30` to see the error |
| Prowlarr indexer fails | Cloudflare protection | Verify FlareSolverr is running: `curl http://SERVER_IP:8191` |
| Downloads stuck in queue | No seeds / stalled | Decluttarr should auto-clean. Check its logs: `docker logs decluttarr --tail 20` |
| Plex can't find new media | Library paths wrong | Verify Plex library paths match disk mount points. Manual scan: Plex → Libraries → Scan |
| Addon can't reach *arr | UFW blocking Docker bridge | Add UFW rule: `ufw allow from DOCKER_SUBNET to any port PORT` |
| Lidarr plugins missing | Using stable image | Must use `lidarr:nightly`. Check: `docker inspect lidarr --format '{{.Config.Image}}'` |
| Beets import fails | Bad match | Run `beet import -t /path` (timid mode) to preview matches |
| High CPU from Kometa | Normal during nightly run | Takes 15-30 min depending on library size. Runs at 3 AM by default. |
| qBittorrent paused | Temperature protection | Check `journalctl -u qbittorrent-temp-control` — CPU was too hot |
| Unpackerr not extracting | Config paths wrong | Paths in `unpackerr.conf` must match host paths, not container paths |

---

## Backup & Restore

### What to Back Up

| Item | Path | Importance |
|---|---|---|
| *arr databases | `/opt/mediaserver/config/{radarr,sonarr,lidarr,prowlarr,bazarr}/` | Critical — contains all library metadata, history |
| Plex config | `/opt/mediaserver/config/plex/` | Critical — contains server identity, watch history, metadata |
| Docker Compose files | `/opt/mediaserver/docker-compose*.yml` | Important — the deployment definition |
| `.env` file | `/opt/mediaserver/.env` | Critical — all credentials |
| Beets database | `~/.config/beets/library.db` | Important — import history |
| Watchdog scripts | `/usr/local/bin/arr_watchdog.sh` | Easy to recreate from repo |
| Systemd units | `/etc/systemd/system/arr-watchdog.service` etc. | Easy to recreate from repo |

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/path/to/backups/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# Stop containers to ensure clean database state
cd /opt/mediaserver
docker compose -f docker-compose.yml stop
docker compose -f docker-compose-addons.yml stop

# Backup configs
tar -czf "$BACKUP_DIR/mediaserver-config.tar.gz" /opt/mediaserver/config/
cp /opt/mediaserver/.env "$BACKUP_DIR/"
cp /opt/mediaserver/docker-compose*.yml "$BACKUP_DIR/"
cp ~/.config/beets/library.db "$BACKUP_DIR/"

# Restart
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose-addons.yml up -d

echo "Backup complete: $BACKUP_DIR"
```

### Restore

```bash
# Deploy fresh stack (Steps 1-4)
# Then stop containers and restore config:
docker compose -f docker-compose.yml stop
docker compose -f docker-compose-addons.yml stop

tar -xzf mediaserver-config.tar.gz -C /
cp .env /opt/mediaserver/
cp library.db ~/.config/beets/

docker compose -f docker-compose.yml up -d
docker compose -f docker-compose-addons.yml up -d
```

---

## Resource Usage

Estimated resource consumption on the ThinkCentre:

| State | RAM | CPU |
|---|---|---|
| Idle (all containers running, no activity) | ~2.5 GB | <5% |
| Active downloading (qBittorrent + *arr importing) | ~3.5 GB | 10-20% |
| Plex transcoding (1 stream, hardware) | ~4 GB | 15-30% |
| Plex transcoding (1 stream, software) | ~5 GB | 60-90% |
| Kometa nightly run | +1.5 GB spike | +20-40% for ~15-30 min |
| Peak (transcode + Kometa + downloads) | ~6-7 GB | 70-100% |

**Disk I/O:** During imports and transcoding, expect sustained reads/writes. An SSD for `/opt/mediaserver/config/` (databases) is strongly recommended; media storage can be HDD.

---

## Migration Status

The stack is being migrated from CLAU (desktop) to ThinkCentre (server). Current state:

| Component | Status | Location |
|---|---|---|
| qBittorrent | Migrated | ThinkCentre (systemd) |
| Plex | **Dual-running** | ThinkCentre (Docker) + CLAU (legacy) |
| Physical disks | Migrated | ThinkCentre |
| Magnet handler | Migrated | ThinkCentre |
| Temp controller | Migrated | ThinkCentre |
| Samba | Migrated | ThinkCentre |
| All *arr apps | Migrated | ThinkCentre (Docker) |
| All addons | New | ThinkCentre (Docker) |
| Nicotine+ (Soulseek) | **Pending** | Still on CLAU |
| Plex (disable on CLAU) | **Pending** | CLAU → will be deactivated |

**End state:** All media services run on ThinkCentre. CLAU only runs Nicotine+ (Soulseek), NordVPN, Tailscale, and desktop tools.

---

## License

MIT
