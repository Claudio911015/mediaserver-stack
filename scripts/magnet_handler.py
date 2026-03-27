#!/usr/bin/env python3
"""
Magnet link interceptor for qBittorrent.
Detects category automatically from torrent name and adds it via WebAPI.

Install as xdg handler:
  sudo cp magnet_handler.py /usr/local/bin/magnet-handler
  sudo chmod +x /usr/local/bin/magnet-handler

Then register as the magnet: URI handler:
  xdg-mime default magnet-handler.desktop x-scheme-handler/magnet

Environment variables:
  QBIT_URL  → qBittorrent WebUI URL (default: http://localhost:8080)
"""

import sys
import re
import os
import urllib.parse
import subprocess
import requests

QBIT_URL = os.environ.get("QBIT_URL", "http://localhost:8080")

# Save paths by category — adjust to your disk layout
SAVE_PATHS = {
    "Series":    "/media/user/disk/series",
    "Movies":    "/media/user/disk/peliculas",
    "Music":     "/media/user/disk/musica",
    "Audiobook": "/media/user/disk/audiolibros",
    "Books":     "/media/user/disk/libros",
}

# Category detection rules (order matters: Series before Movies)
RULES = [
    ("Series", [
        r'\bS\d+E\d+\b',
        r'\b\d+x\d+\b',
        r'\btemporada\b',
        r'\bseason\b',
        r'\bcomplete.series\b',
        r'\bserie[s]?\b',
    ]),
    ("Music", [
        r'\bFLAC\b',
        r'\bMP3\b',
        r'\bAAC\b',
        r'\bdiscograph(y|ia)\b',
        r'\balbum\b',
        r'\bOST\b',
        r'\blossless\b',
        r'\b320kbps\b',
        r'\b(VA|V\.A\.)\s*-',
    ]),
    ("Audiobook", [
        r'\baudiobook\b',
        r'\baudio\s*book\b',
        r'\bunabridged\b',
        r'\bnarrated\b',
        r'\blibro\s*audio\b',
    ]),
    ("Books", [
        r'\bepub\b',
        r'\bmobi\b',
        r'\bebook\b',
        r'\be-book\b',
        r'\bpdf\b',
    ]),
    ("Movies", [
        r'\b(1080p|720p|4K|2160p|480p)\b',
        r'\b(BluRay|BDRip|WEBRip|WEB-DL|HDRip|DVDRip|HDCAM)\b',
        r'\b(x264|x265|HEVC|H\.264|H\.265|XviD|DivX)\b',
        r'\b(REMUX|UHD)\b',
    ]),
]

def detect_category(name):
    for category, patterns in RULES:
        for pattern in patterns:
            if re.search(pattern, name, re.IGNORECASE):
                return category
    return ""

def add_torrent(magnet, category):
    try:
        data = {"urls": magnet, "category": category}
        if category in SAVE_PATHS:
            data["savepath"] = SAVE_PATHS[category]
        r = requests.post(f"{QBIT_URL}/api/v2/torrents/add", data=data, timeout=5)
        return r.text.strip() == "Ok."
    except Exception:
        return False

def notify(title, message):
    subprocess.Popen(["notify-send", "-i", "qbittorrent", title, message])

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    magnet = sys.argv[1]

    dn_match = re.search(r'[?&]dn=([^&]+)', magnet)
    name = urllib.parse.unquote_plus(dn_match.group(1)) if dn_match else ""

    category = detect_category(name)

    if add_torrent(magnet, category):
        if category:
            notify("qBittorrent", f"Added: {name[:60]}\nCategory: {category}")
        else:
            notify("qBittorrent", f"Added: {name[:60]}\nNo category detected")
    else:
        subprocess.Popen(["qbittorrent", magnet])

if __name__ == "__main__":
    main()
