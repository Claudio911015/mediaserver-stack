#!/usr/bin/env python3
"""
Retry adding artists to Lidarr from /tmp/lidarr_retry.txt.
One artist name per line.

Environment variables:
  LIDARR_URL  → Lidarr base URL  (default: http://localhost:8686)
  LIDARR_KEY  → Lidarr API key
"""
import json, time, unicodedata, re, os
import urllib.request, urllib.parse, urllib.error

API     = f"{os.environ.get('LIDARR_URL', 'http://localhost:8686')}/api/v1"
KEY     = os.environ.get("LIDARR_KEY", "")
HEADERS = {"X-Api-Key": KEY, "Content-Type": "application/json"}

ROOT_FOLDER_PATH    = os.environ.get("LIDARR_ROOT", "/music")
QUALITY_PROFILE_ID  = int(os.environ.get("LIDARR_QUALITY_PROFILE", "2"))
METADATA_PROFILE_ID = int(os.environ.get("LIDARR_METADATA_PROFILE", "1"))

def normalize(name):
    n = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', n)

def api_get(path):
    req = urllib.request.Request(f"{API}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def api_post(path, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(f"{API}{path}", data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

with open('/tmp/lidarr_retry.txt') as f:
    to_add = [l.strip() for l in f if l.strip()]

existing = {normalize(a['artistName']) for a in api_get("/artist")}

added, not_found, errors = 0, [], []
for i, name in enumerate(to_add):
    if normalize(name) in existing:
        print(f"  [{i+1}/{len(to_add)}] SKIP: {name}")
        continue
    try:
        results = api_get(f"/artist/lookup?term={urllib.parse.quote(name)}")
        if not results:
            not_found.append(name)
            print(f"  [{i+1}/{len(to_add)}] NOT FOUND: {name}")
            time.sleep(1)
            continue
        artist = next((r for r in results if normalize(r.get('artistName','')) == normalize(name)), results[0])
        payload = {
            "artistName":        artist.get('artistName'),
            "foreignArtistId":   artist.get('foreignArtistId'),
            "qualityProfileId":  QUALITY_PROFILE_ID,
            "metadataProfileId": METADATA_PROFILE_ID,
            "monitored":         True,
            "monitor":           "all",
            "rootFolderPath":    ROOT_FOLDER_PATH,
            "addOptions": {"monitor": "all", "searchForMissingAlbums": False},
            "links":   artist.get('links', []),
            "genres":  artist.get('genres', []),
            "ratings": artist.get('ratings', {}),
            "images":  artist.get('images', []),
        }
        api_post("/artist", payload)
        added += 1
        print(f"  [{i+1}/{len(to_add)}] ✓ {name}")
    except Exception as ex:
        errors.append(f"{name}: {ex}")
        print(f"  [{i+1}/{len(to_add)}] ERROR: {name}: {ex}")
    time.sleep(1)

print(f"\nAdded: {added} | Not found: {len(not_found)} | Errors: {len(errors)}")
