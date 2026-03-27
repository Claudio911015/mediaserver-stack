#!/usr/bin/env python3
"""
Downloads artist thumbnails from Plex and copies them to Lidarr's MediaCover directory.
Useful for populating Lidarr artist images from an existing Plex music library.

Environment variables:
  PLEX_URL       → Plex URL                  (default: http://localhost:32400)
  PLEX_TOKEN     → Plex auth token
  LIDARR_URL     → Lidarr base URL           (default: http://localhost:8686)
  LIDARR_KEY     → Lidarr API key
  LIDARR_HOST    → SSH host for Lidarr       (default: localhost — set if Lidarr is remote)
  LIDARR_MC_PATH → Lidarr MediaCover path    (default: /config/MediaCover)
"""
import json, unicodedata, re, subprocess, tempfile, os
import urllib.request, urllib.parse
from pathlib import Path

PLEX_URL    = os.environ.get("PLEX_URL",       "http://localhost:32400")
PLEX_TOKEN  = os.environ.get("PLEX_TOKEN",     "")
LIDARR_API  = f"{os.environ.get('LIDARR_URL', 'http://localhost:8686')}/api/v1"
LIDARR_KEY  = os.environ.get("LIDARR_KEY",     "")
LIDARR_HOST = os.environ.get("LIDARR_HOST",    "")   # e.g. "user@192.168.1.100" or empty for local
LIDARR_MC   = os.environ.get("LIDARR_MC_PATH", "/config/MediaCover")

def normalize(name):
    n = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', n)

def plex_get(path):
    url = f"{PLEX_URL}{path}?X-Plex-Token={PLEX_TOKEN}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)

# 1. Find Lidarr artists without images
print("Finding Lidarr artists without images...")
with urllib.request.urlopen(
    urllib.request.Request(f"{LIDARR_API}/artist", headers={"X-Api-Key": LIDARR_KEY}),
    timeout=15
) as r:
    artists = json.load(r)
no_img = {normalize(a['artistName']): a for a in artists if not a.get('images')}
print(f"  Without image: {len(no_img)}")

# 2. Get Plex artists with thumbnails
print("Getting artists from Plex...")
sections     = plex_get("/library/sections")['MediaContainer']['Directory']
music_sections = [s['key'] for s in sections if s.get('type') == 'artist']
print(f"  Music sections: {music_sections}")

plex_artists = {}
for sec in music_sections:
    data = plex_get(f"/library/sections/{sec}/all")['MediaContainer']
    for item in data.get('Metadata', []):
        thumb = item.get('thumb') or item.get('art')
        if thumb:
            plex_artists[normalize(item['title'])] = (item['title'], thumb)

print(f"  With image: {len(plex_artists)}")

# 3. Match, download and copy
matched, not_found = 0, []

for norm, artist in no_img.items():
    if norm not in plex_artists:
        not_found.append(artist['artistName'])
        continue

    plex_title, thumb_path = plex_artists[norm]
    lid     = artist['id']
    img_url = f"{PLEX_URL}{thumb_path}?X-Plex-Token={PLEX_TOKEN}&width=500&height=500"

    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        urllib.request.urlretrieve(img_url, tmp_path)
        if os.path.getsize(tmp_path) < 1000:
            not_found.append(artist['artistName'])
            continue

        remote_dir  = f"{LIDARR_MC}/{lid}"
        remote_file = f"{remote_dir}/poster.jpg"

        if LIDARR_HOST:
            # Remote Lidarr over SSH
            subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no",
                            LIDARR_HOST, f"mkdir -p {remote_dir}"], capture_output=True)
            scp = subprocess.run(["scp", "-o", "StrictHostKeyChecking=no",
                                  tmp_path, f"{LIDARR_HOST}:{remote_file}"],
                                 capture_output=True)
            ok = scp.returncode == 0
        else:
            # Local Lidarr
            Path(remote_dir).mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(tmp_path, remote_file)
            ok = True

        if ok:
            print(f"  ✓ {artist['artistName']}  ←  {plex_title}")
            matched += 1
        else:
            print(f"  ✗ {artist['artistName']}")
            not_found.append(artist['artistName'])
    finally:
        os.unlink(tmp_path)

print(f"\n=== Results ===")
print(f"Copied:    {matched}")
print(f"No match:  {len(not_found)}")
if not_found:
    print("\nNo match (first 30):")
    for n in sorted(not_found)[:30]:
        print(f"  - {n}")
