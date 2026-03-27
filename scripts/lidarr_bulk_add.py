#!/usr/bin/env python3
"""
Bulk add artists to Lidarr from a list of folder names.

Reads /tmp/lidarr_artists_to_add.txt (first line: total count, rest: artist names)
and /tmp/lidarr_existing.txt (one artist name per line, already in Lidarr).

Environment variables:
  LIDARR_URL  → Lidarr base URL  (default: http://localhost:8686)
  LIDARR_KEY  → Lidarr API key
"""
import json, time, unicodedata, re, os
import urllib.request, urllib.parse, urllib.error

API     = f"{os.environ.get('LIDARR_URL', 'http://localhost:8686')}/api/v1"
KEY     = os.environ.get("LIDARR_KEY", "")
HEADERS = {"X-Api-Key": KEY, "Content-Type": "application/json"}

ROOT_FOLDER_PATH   = os.environ.get("LIDARR_ROOT", "/music")
QUALITY_PROFILE_ID = int(os.environ.get("LIDARR_QUALITY_PROFILE", "2"))
METADATA_PROFILE_ID = int(os.environ.get("LIDARR_METADATA_PROFILE", "1"))

def normalize(name):
    n = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]', '', n)

def api_get(path):
    req = urllib.request.Request(f"{API}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

def api_post(path, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(f"{API}{path}", data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

with open('/tmp/lidarr_artists_to_add.txt') as f:
    lines = f.read().splitlines()
    candidates = lines[1:]

with open('/tmp/lidarr_existing.txt') as f:
    existing_norm = {normalize(l.strip()) for l in f if l.strip()}

to_add = [c for c in candidates if normalize(c) not in existing_norm and '.' not in c.split('/')[-1]]

print(f"Candidates: {len(candidates)}")
print(f"Already in Lidarr: {len(existing_norm)}")
print(f"To add: {len(to_add)}")
print()

added, skipped, not_found, errors = [], [], [], []

for i, folder_name in enumerate(to_add):
    try:
        query   = urllib.parse.quote(folder_name)
        results = api_get(f"/artist/lookup?term={query}")

        if not results:
            not_found.append(folder_name)
            print(f"  [{i+1}/{len(to_add)}] NOT FOUND: {folder_name}")
            time.sleep(0.3)
            continue

        artist      = results[0]
        artist_name = artist.get('artistName', '')

        if normalize(artist_name) != normalize(folder_name):
            exact = next((r for r in results if normalize(r.get('artistName','')) == normalize(folder_name)), None)
            if exact:
                artist      = exact
                artist_name = artist.get('artistName', '')

        payload = {
            "artistName":        artist.get('artistName'),
            "foreignArtistId":   artist.get('foreignArtistId'),
            "mbId":              artist.get('foreignArtistId'),
            "artistSlug":        artist.get('artistSlug', ''),
            "qualityProfileId":  QUALITY_PROFILE_ID,
            "metadataProfileId": METADATA_PROFILE_ID,
            "monitored":         True,
            "monitor":           "all",
            "rootFolderPath":    ROOT_FOLDER_PATH,
            "addOptions": {"monitor": "all", "searchForMissingAlbums": False},
            "links":    artist.get('links', []),
            "genres":   artist.get('genres', []),
            "ratings":  artist.get('ratings', {}),
            "statistics": {},
            "images":   artist.get('images', []),
        }

        try:
            api_post("/artist", payload)
            added.append(f"{folder_name} → {artist_name}")
            print(f"  [{i+1}/{len(to_add)}] ✓ {folder_name} → {artist_name}")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if 'already exists' in body.lower() or '409' in str(e.code):
                skipped.append(folder_name)
                print(f"  [{i+1}/{len(to_add)}] SKIP (exists): {folder_name}")
            else:
                errors.append(f"{folder_name}: {e.code} {body[:80]}")
                print(f"  [{i+1}/{len(to_add)}] ERROR {e.code}: {folder_name}: {body[:60]}")

        time.sleep(0.5)

    except Exception as ex:
        errors.append(f"{folder_name}: {ex}")
        print(f"  [{i+1}/{len(to_add)}] EXCEPTION: {folder_name}: {ex}")
        time.sleep(0.5)

print(f"\n=== FINAL RESULTS ===")
print(f"Added:       {len(added)}")
print(f"Skipped:     {len(skipped)}")
print(f"Not in MB:   {len(not_found)}")
print(f"Errors:      {len(errors)}")
if not_found:
    print(f"\nNot found (first 30):")
    for n in not_found[:30]: print(f"  - {n}")
if errors:
    print(f"\nErrors:")
    for e in errors[:10]: print(f"  - {e}")
