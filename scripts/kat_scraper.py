#!/usr/bin/env python3
"""
KickassTorrents scraper → qBittorrent

Usage:
  python3 kat_scraper.py <query> [--category CAT] [--savepath PATH] [--dry-run]

Examples:
  python3 kat_scraper.py "pink floyd"
  python3 kat_scraper.py "the godfather" --category Movies
  python3 kat_scraper.py "breaking bad" --savepath /media/user/disk/series --dry-run

Defaults:
  --category  → query normalized (lowercase, spaces→underscores)
  --savepath  → MEDIA_DISK/downloads/<category>  (reads MEDIA_DISK env var)

Environment variables:
  QBIT_URL   → qBittorrent WebUI URL  (default: http://localhost:8080)
  QBIT_USER  → qBittorrent username   (default: admin)
  QBIT_PASS  → qBittorrent password
  MEDIA_DISK → base media path        (default: /media/user/disk)
"""
import re, time, sys, os, argparse, urllib.request, urllib.parse, http.cookiejar

BASE_URL  = "https://kickasstorrents.to"
HEADERS   = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
QBIT_URL  = os.environ.get("QBIT_URL",  "http://localhost:8080")
QBIT_USER = os.environ.get("QBIT_USER", "admin")
QBIT_PASS = os.environ.get("QBIT_PASS", "")
MEDIA_DISK = os.environ.get("MEDIA_DISK", "/media/user/disk")

# --- CLI ---
parser = argparse.ArgumentParser(description="KAT scraper → qBittorrent")
parser.add_argument("query", help="Search term")
parser.add_argument("--category", default=None, help="qBittorrent category (default: normalized query)")
parser.add_argument("--savepath", default=None, help="Download path (default: MEDIA_DISK/downloads/<category>)")
parser.add_argument("--dry-run", action="store_true", help="List magnets only, do not send to qBittorrent")
args = parser.parse_args()

query     = args.query
category  = args.category or re.sub(r'\s+', '_', query.strip().lower())
savepath  = args.savepath or f"{MEDIA_DISK}/downloads/{category}"
dry_run   = args.dry_run

query_encoded = urllib.parse.quote(query)
SEARCH_URL    = f"{BASE_URL}/usearch/{query_encoded}/"
OUT_FILE      = f"/tmp/kat_{category}_magnets.txt"

print(f"Query:    {query}")
print(f"Category: {category}")
print(f"Savepath: {savepath}")
print(f"Output:   {OUT_FILE}")
print(f"Dry-run:  {dry_run}")
print()

# --- qBittorrent ---
qbit_opener = None

def qbit_login():
    global qbit_opener
    jar    = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    data   = urllib.parse.urlencode({"username": QBIT_USER, "password": QBIT_PASS}).encode()
    opener.open(f"{QBIT_URL}/api/v2/auth/login", data, timeout=10)
    qbit_opener = opener

def qbit_ensure_category():
    data = urllib.parse.urlencode({"category": category, "savePath": savepath}).encode()
    req  = urllib.request.Request(f"{QBIT_URL}/api/v2/torrents/createCategory", data=data)
    try:
        qbit_opener.open(req, timeout=10)
    except Exception:
        req2 = urllib.request.Request(f"{QBIT_URL}/api/v2/torrents/editCategory", data=data)
        try:
            qbit_opener.open(req2, timeout=10)
        except Exception:
            pass

def qbit_add(magnet):
    data = urllib.parse.urlencode({
        "urls": magnet,
        "category": category,
        "savepath": savepath,
    }).encode()
    req = urllib.request.Request(f"{QBIT_URL}/api/v2/torrents/add", data=data)
    with qbit_opener.open(req, timeout=10) as r:
        return r.read().decode().strip()

# --- KAT helpers ---
def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="ignore")

def get_detail_links(html):
    links = re.findall(r'href="(/(?!download/)[^"]*-t\d+\.html)"', html)
    return list(dict.fromkeys(links))

def get_next_page(html, page):
    nums = [int(n) for n in re.findall(
        r'href="/usearch/' + re.escape(query_encoded) + r'/(\d+)/"', html
    )]
    if not nums:
        nums = [int(n) for n in re.findall(r'/usearch/[^/]+/(\d+)/', html)]
    return page + 1 if nums and page < max(nums) else None

def get_magnet(html):
    m = re.search(r'(magnet:\?[^\s"\'<>]*xt=urn[^\s"\'<>]*)', html)
    return m.group(1) if m else None

# --- Main ---
if not dry_run:
    qbit_login()
    qbit_ensure_category()

seen = set()
page = 1
sent = 0

with open(OUT_FILE, "w") as f:
    while True:
        url = SEARCH_URL if page == 1 else f"{SEARCH_URL}{page}/"
        print(f"[page {page}] {url}", flush=True)
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  Error: {e}"); break

        links = get_detail_links(html)
        if not links:
            print("  No results, done.")
            break

        for path in links:
            if path in seen:
                continue
            seen.add(path)
            try:
                detail = fetch(BASE_URL + path)
                magnet = get_magnet(detail)
                if magnet:
                    f.write(magnet + "\n")
                    f.flush()
                    if dry_run:
                        print(f"  [DRY] {path.split('/')[1][:65]}", flush=True)
                    else:
                        result = qbit_add(magnet)
                        sent  += 1
                        print(f"  +qbit [{sent}] {path.split('/')[1][:60]} → {result}", flush=True)
                time.sleep(0.3)
            except Exception as e:
                print(f"  ERR {path}: {e}")
                time.sleep(1)

        next_p = get_next_page(html, page)
        if not next_p:
            break
        page = next_p
        time.sleep(0.5)

total = sum(1 for _ in open(OUT_FILE))
suffix = "  (dry-run, not sent)" if dry_run else f' sent → category "{category}"'
print(f"\nTotal: {total} magnets{suffix}")
print(f"Saved to: {OUT_FILE}")
