#!/usr/bin/env python3
"""Search public Pinterest pins (no login, no API key) and optionally download them.

Usage:
  python3 pinterest_search.py "brutalist poster" --limit 30
  python3 pinterest_search.py "brutalist poster" --download 12 --sheet --out ./references
  python3 pinterest_search.py "brutalist poster" --pick 2,5,11 --size orig
  python3 pinterest_search.py "brutalist poster" --json

Default output: one line per pin -> index, width x height, dominant color, original image URL.
Downloads also produce <slug>-refs.md (table of the saved pins) and, with --sheet and Pillow
installed, <slug>-sheet.jpg (numbered contact sheet).

Uses Pinterest's internal web endpoint (BaseSearchResource); it may change without notice.
"""
import argparse
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = "https://www.pinterest.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def _read(resp):
    body = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)
    return body


class Pinterest:
    def __init__(self):
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.opener.addheaders = [("User-Agent", UA), ("Accept-Language", "en-US,en;q=0.9")]
        html = _read(self.opener.open(BASE + "/", timeout=30)).decode("utf-8", "ignore")
        m = re.search(r'"appVersion":"([0-9a-f]+)"', html)
        self.app_version = m.group(1) if m else ""
        self.csrf = next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def search(self, query, bookmark=None, page_size=25):
        src = "/search/pins/?q=" + urllib.parse.quote(query)
        data = json.dumps({"options": {"query": query, "scope": "pins",
                                       "bookmarks": [bookmark] if bookmark else [],
                                       "page_size": page_size, "redux_normalize_feed": True,
                                       "rs": "typed", "source_url": src},
                           "context": {}})
        url = BASE + "/resource/BaseSearchResource/get/?" + urllib.parse.urlencode(
            {"source_url": src, "data": data, "_": str(int(time.time() * 1000))})
        req = urllib.request.Request(url, headers={
            "Accept": "application/json, text/javascript, */*, q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "X-Pinterest-AppState": "active",
            "X-APP-VERSION": self.app_version,
            "X-CSRFToken": self.csrf,
            # These two headers are what distinguishes an accepted request from a 403.
            "x-pinterest-source-url": src,
            "x-pinterest-pws-handler": "www/search/[scope].js",
            "Referer": BASE + src,
        })
        j = json.loads(_read(self.opener.open(req, timeout=30)))
        rr = j["resource_response"]
        pins = []
        for p in rr.get("data", {}).get("results", []):
            if p.get("type") != "pin" or "images" not in p:
                continue
            orig = p["images"].get("orig") or {}
            mid = p["images"].get("736x") or orig
            pins.append({
                "id": p.get("id"),
                "signature": p.get("image_signature"),
                "width": orig.get("width"), "height": orig.get("height"),
                "color": p.get("dominant_color"),
                "orig": orig.get("url"), "medium": mid.get("url"),
            })
        return pins, rr.get("bookmark")

    def search_many(self, query, limit):
        """Paginate until `limit` pins. Logged-out search returns nothing for some exact
        phrasings, so an empty first page falls back to natural variants of the query."""
        for q in self._variants(query):
            out, seen, bm = [], set(), None
            for _ in range(10):
                pins, bm = self.search(q, bm)
                for p in pins:
                    if p["signature"] in seen:
                        continue
                    seen.add(p["signature"])
                    out.append(p)
                if len(out) >= limit or not bm or bm == "-end-":
                    break
            if out:
                if q != query:
                    print(f"No results for '{query}'; using '{q}' instead.", file=sys.stderr)
                return out[:limit]
        return []

    @staticmethod
    def _variants(query):
        words = query.split()
        yield query
        yield query + " design inspiration"
        yield query + " ideas"
        if len(words) > 2:
            yield " ".join(words[:-1])
            yield " ".join(words[1:])

    def download(self, pin, path, size="medium"):
        urls = (pin["orig"], pin["medium"]) if size == "orig" else (pin["medium"], pin["orig"])
        for url in urls:
            if not url:
                continue
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE + "/"})
                body = _read(self.opener.open(req, timeout=60))
                ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".jpg"
                final = path + ext
                with open(final, "wb") as f:
                    f.write(body)
                return final
            except Exception:
                continue
        return None


def contact_sheet(files, out, cell=360, cols=4):
    """Numbered grid of the downloaded images, so one read shows the whole batch."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed; contact sheet skipped (pip install pillow).", file=sys.stderr)
        return None
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), "white")
    draw = ImageDraw.Draw(sheet)
    for n, f in enumerate(files):
        try:
            im = Image.open(f).convert("RGB")
        except Exception:
            continue
        im.thumbnail((cell - 8, cell - 8))
        x, y = (n % cols) * cell + 4, (n // cols) * cell + 4
        sheet.paste(im, (x, y))
        label = os.path.basename(f).rsplit(".", 1)[0].rsplit("-", 1)[-1]
        draw.rectangle([x, y, x + 34, y + 20], fill="black")
        draw.text((x + 6, y + 4), label, fill="white")
    sheet.save(out, quality=85)
    return out


def write_refs_md(query, pins, idx, files, out):
    """Markdown table of the downloaded pins, ready to paste into a brief."""
    lines = [f"# References: {query}", "", "| # | file | size | color | url |", "|---|---|---|---|---|"]
    for i, f in zip(idx, files):
        p = pins[i]
        size = f"{p['width'] or '?'}x{p['height'] or '?'}"
        lines.append(f"| {i:02d} | {os.path.basename(f)} | {size} | {p['color'] or ''} | {p['orig'] or p['medium']} |")
    lines.append("")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--limit", type=int, default=30, help="how many pins to list (up to ~250)")
    ap.add_argument("--download", type=int, default=0, help="download the first N pins")
    ap.add_argument("--pick", default="", help="download only these indexes, e.g. 2,5,11")
    ap.add_argument("--out", default="./references", help="download folder")
    ap.add_argument("--prefix", default="", help="file prefix (default: slug of the query)")
    ap.add_argument("--size", choices=["medium", "orig"], default="medium",
                    help="medium = 736px wide (default, enough for reference); orig = full size")
    ap.add_argument("--sheet", action="store_true", help="also build a contact sheet (needs Pillow)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the table")
    a = ap.parse_args()

    pt = Pinterest()
    pins = pt.search_many(a.query, a.limit)
    if not pins:
        print("No pins found (the endpoint may have changed, or the query returned no images).", file=sys.stderr)
        sys.exit(1)

    if a.json:
        print(json.dumps(pins, ensure_ascii=False, indent=1))
    else:
        for i, p in enumerate(pins):
            print(f"{i:>3}  {p['width'] or '?':>5}x{p['height'] or '?':<5} {p['color'] or '':8} {p['orig'] or p['medium']}")

    idx = []
    if a.pick:
        idx = [int(x) for x in a.pick.split(",") if x.strip().isdigit()]
    elif a.download:
        idx = list(range(min(a.download, len(pins))))
    idx = [i for i in idx if i < len(pins)]
    if not idx:
        return

    os.makedirs(a.out, exist_ok=True)
    prefix = a.prefix or re.sub(r"[^a-z0-9]+", "-", a.query.lower()).strip("-")[:40]
    saved_idx, saved = [], []
    for i in idx:
        f = pt.download(pins[i], os.path.join(a.out, f"{prefix}-{i:02d}"), a.size)
        if f:
            saved_idx.append(i)
            saved.append(f)
    print("", file=sys.stderr)
    print("Downloaded:", file=sys.stderr)
    for f in saved:
        print(f)
    if saved:
        print(write_refs_md(a.query, pins, saved_idx, saved, os.path.join(a.out, f"{prefix}-refs.md")))
        if a.sheet:
            sheet = contact_sheet(saved, os.path.join(a.out, f"{prefix}-sheet.jpg"))
            if sheet:
                print(sheet)


if __name__ == "__main__":
    main()
