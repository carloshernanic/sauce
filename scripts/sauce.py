#!/usr/bin/env python3
"""Search visual references on Pinterest, Dribbble and Cosmos (no login, no API key),
list them, download them, and build a numbered contact sheet.

Usage:
  python3 sauce.py "brutalist poster"                          # Pinterest (default)
  python3 sauce.py "brutalist poster" --source all --limit 12  # every source, 12 each
  python3 sauce.py "fintech dashboard" --source dribbble,cosmos --download 8 --sheet
  python3 sauce.py "japandi living room" --pick 2,5,11 --size orig --out ./refs
  python3 sauce.py "editorial layout" --json

Default output: one line per reference -> index, source, width x height, dominant color,
title, image URL. Downloads also produce <slug>-refs.md (table of the saved references,
with page links and authors when the source provides them) and, with --sheet and Pillow
installed, <slug>-sheet.jpg (numbered contact sheet).

All sources use the public web endpoints the sites' own logged-out pages call; any of
them may change without notice. Sites that forbid automated access are not included.
"""
import argparse
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def _read(resp):
    body = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)
    return body


def _opener():
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    op.addheaders = [("User-Agent", UA), ("Accept-Language", "en-US,en;q=0.9")]
    return op


def _slug(text, n=40):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n]


def query_variants(query):
    """Logged-out search returns nothing for some exact phrasings; try natural variants."""
    words = query.split()
    yield query
    yield query + " design inspiration"
    yield query + " ideas"
    if len(words) > 2:
        yield " ".join(words[:-1])
        yield " ".join(words[1:])


def ref(source, id, image, medium=None, width=None, height=None, color=None,
        title="", author="", page=""):
    return {"source": source, "id": str(id), "title": (title or "").strip(),
            "author": (author or "").strip(), "page": page or "",
            "width": width, "height": height, "color": color,
            "image": image, "medium": medium or image}


# --------------------------------------------------------------------------- Pinterest
class Pinterest:
    name = "pinterest"
    BASE = "https://www.pinterest.com"

    def __init__(self):
        self.op = _opener()
        html_ = _read(self.op.open(self.BASE + "/", timeout=30)).decode("utf-8", "ignore")
        m = re.search(r'"appVersion":"([0-9a-f]+)"', html_)
        self.app_version = m.group(1) if m else ""
        self.csrf = next((c.value for c in self.op.handlers[-1].cookiejar
                          if c.name == "csrftoken"), "") if hasattr(self.op.handlers[-1], "cookiejar") else ""
        if not self.csrf:
            for h in self.op.handlers:
                if hasattr(h, "cookiejar"):
                    self.csrf = next((c.value for c in h.cookiejar if c.name == "csrftoken"), "")

    def _page(self, query, bookmark=None, page_size=25):
        src = "/search/pins/?q=" + urllib.parse.quote(query)
        data = json.dumps({"options": {"query": query, "scope": "pins",
                                       "bookmarks": [bookmark] if bookmark else [],
                                       "page_size": page_size, "redux_normalize_feed": True,
                                       "rs": "typed", "source_url": src},
                           "context": {}})
        url = self.BASE + "/resource/BaseSearchResource/get/?" + urllib.parse.urlencode(
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
            "Referer": self.BASE + src,
        })
        rr = json.loads(_read(self.op.open(req, timeout=30)))["resource_response"]
        out = []
        for p in rr.get("data", {}).get("results", []):
            if p.get("type") != "pin" or "images" not in p:
                continue
            orig = p["images"].get("orig") or {}
            mid = p["images"].get("736x") or orig
            out.append(ref("pinterest", p.get("image_signature") or p.get("id"),
                           orig.get("url"), mid.get("url"), orig.get("width"), orig.get("height"),
                           p.get("dominant_color")))
        return out, rr.get("bookmark")

    def search(self, query, limit):
        for q in query_variants(query):
            out, seen, bm = [], set(), None
            for _ in range(10):
                pins, bm = self._page(q, bm)
                for p in pins:
                    if p["id"] in seen:
                        continue
                    seen.add(p["id"])
                    out.append(p)
                if len(out) >= limit or not bm or bm == "-end-":
                    break
            if out:
                if q != query:
                    print(f"[pinterest] no results for '{query}'; using '{q}'.", file=sys.stderr)
                return out[:limit]
        return []


# --------------------------------------------------------------------------- Dribbble
class Dribbble:
    name = "dribbble"
    BASE = "https://dribbble.com"

    def __init__(self):
        self.op = _opener()

    def _page(self, query, page):
        url = f"{self.BASE}/search/{_slug(query, 80)}?page={page}&per_page=24"
        req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "X-Requested-With": "XMLHttpRequest"})
        text = _read(self.op.open(req, timeout=30)).decode("utf-8", "ignore")
        out = []
        for m in re.finditer(r'<li\s+id="screenshot-(\d+)"(.*?)</li>', text, re.S):
            sid, card = m.group(1), m.group(2)
            srcset = re.search(r'data-srcset="([^"]+)"', card)
            base = re.search(r'(https://cdn\.dribbble\.com/userupload/[^"?\s]+\.(?:png|jpe?g|gif|webp))', card, re.I)
            if not base:  # video-only shots have no still we can use
                continue
            base = html.unescape(base.group(1))
            medium = base + "?format=webp&resize=1200x900&vertical=center" if srcset else base
            title = re.search(r'class="shot-title">\s*(.*?)\s*<', card, re.S)
            color = re.search(r'background-color:\s*(#[0-9a-fA-F]{6})', card)
            author = re.search(r'class="display-name">\s*(.*?)\s*<', card, re.S)
            link = re.search(r'href="(/shots/[^"]+)"', card)
            out.append(ref("dribbble", sid, base, medium, None, None,
                           color.group(1).lower() if color else None,
                           html.unescape(title.group(1)) if title else "",
                           html.unescape(author.group(1)) if author else "",
                           self.BASE + link.group(1) if link else ""))
        return out

    def search(self, query, limit):
        out, seen = [], set()
        for page in range(1, 6):
            try:
                items = self._page(query, page)
            except urllib.error.HTTPError as e:
                print(f"[dribbble] HTTP {e.code} on page {page}", file=sys.stderr)
                break
            if not items:
                break
            for it in items:
                if it["id"] not in seen:
                    seen.add(it["id"])
                    out.append(it)
            if len(out) >= limit:
                break
        return out[:limit]


# --------------------------------------------------------------------------- Cosmos
class Cosmos:
    """cosmos.so: search returns curated collections ("clusters"); we then pull the
    elements of the best-matching collections."""
    name = "cosmos"
    API = "https://api.cosmos.so/graphql"
    Q_SEARCH = """query SearchGlobal($searchTerm: String!) {
      searchClusters(searchTerm: $searchTerm, meta: { pageSize: 10 }) {
        items { id name slug numberOfElements owner { username } cover { url } }
      }
    }"""
    Q_ELEMENTS = """query GetClusterElements($clusterId: ClusterId, $pageSize: Int, $pageCursor: String) {
      clusterConnections(clusterId: $clusterId, meta: { pageSize: $pageSize, pageCursor: $pageCursor }) {
        items { element {
          __typename id shareUrl
          generatedCaption { text }
          owner { username }
          source { url author { username fullName } }
          ... on MediaElementTile { media { __typename url width height } }
        } }
        meta { nextPageCursor count }
      }
    }"""

    def __init__(self):
        self.op = _opener()

    def _gql(self, op, query, variables):
        body = json.dumps({"operationName": op, "query": query, "variables": variables}).encode()
        req = urllib.request.Request(self.API, data=body, headers={
            "Content-Type": "application/json", "Accept": "application/json",
            "Origin": "https://www.cosmos.so", "Referer": "https://www.cosmos.so/explore"})
        j = json.loads(_read(self.op.open(req, timeout=30)))
        if j.get("errors"):
            raise RuntimeError(j["errors"][0].get("message"))
        return j["data"]

    def _clusters(self, query):
        """Collection search is literal; fall back to shorter/natural phrasings."""
        words = query.split()
        tried = []
        variants = [query] + ([" ".join(words[:-1]), " ".join(words[1:])] if len(words) > 2 else []) \
            + ([" ".join(words[:2])] if len(words) > 3 else []) + [query + " design"]
        for q in variants:
            if q in tried:
                continue
            tried.append(q)
            items = self._gql("SearchGlobal", self.Q_SEARCH, {"searchTerm": q})["searchClusters"]["items"]
            items = [c for c in items if (c.get("numberOfElements") or 0) >= 3]
            if items:
                if q != query:
                    print(f"[cosmos] no collections for '{query}'; using '{q}'.", file=sys.stderr)
                return items
        return []

    def search(self, query, limit):
        clusters = self._clusters(query)
        clusters.sort(key=lambda c: -(c.get("numberOfElements") or 0))
        out, seen = [], set()
        for c in clusters[:4]:
            cursor = None
            while len(out) < limit:
                page = self._gql("GetClusterElements", self.Q_ELEMENTS,
                                 {"clusterId": c["id"], "pageSize": 24, "pageCursor": cursor})["clusterConnections"]
                for it in page["items"]:
                    e = it["element"]
                    media = e.get("media") or {}
                    if not media.get("url") or media.get("__typename") not in ("StaticImage", None):
                        continue
                    if e["id"] in seen:
                        continue
                    seen.add(e["id"])
                    cap = (e.get("generatedCaption") or {}).get("text") or ""
                    cap = re.sub(r"</?n>", "", cap)
                    src = e.get("source") or {}
                    author = (src.get("author") or {}).get("username") or (e.get("owner") or {}).get("username") or ""
                    out.append(ref("cosmos", e["id"], media["url"], media["url"],
                                   media.get("width"), media.get("height"), None,
                                   cap[:120] or f"from collection '{c['name']}'", author,
                                   e.get("shareUrl") or ""))
                    if len(out) >= limit:
                        break
                cursor = (page.get("meta") or {}).get("nextPageCursor")
                if not cursor:
                    break
            if len(out) >= limit:
                break
        return out[:limit]


SOURCES = {"pinterest": Pinterest, "dribbble": Dribbble, "cosmos": Cosmos}


# --------------------------------------------------------------------------- download & output
def download(op, item, path, size="medium"):
    urls = (item["image"], item["medium"]) if size == "orig" else (item["medium"], item["image"])
    for url in urls:
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://" + urllib.parse.urlparse(url).netloc + "/"})
            resp = op.open(req, timeout=60)
            body = _read(resp)
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0]
            ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(ctype)
            if not ext:
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


def write_refs_md(query, items, idx, files, out):
    lines = [f"# References: {query}", "",
             "| # | source | file | size | color | title | author | page | image |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, f in zip(idx, files):
        p = items[i]
        size = f"{p['width'] or '?'}x{p['height'] or '?'}"
        title = p["title"].replace("|", "/")[:60]
        lines.append(f"| {i:02d} | {p['source']} | {os.path.basename(f)} | {size} | {p['color'] or ''} | {title} | {p['author']} | {p['page']} | {p['image']} |")
    lines.append("")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--source", default="pinterest",
                    help="comma-separated: pinterest, dribbble, cosmos, or all (default: pinterest)")
    ap.add_argument("--limit", type=int, default=30, help="how many references per source")
    ap.add_argument("--download", type=int, default=0, help="download the first N references (across sources, interleaved)")
    ap.add_argument("--pick", default="", help="download only these indexes, e.g. 2,5,11")
    ap.add_argument("--out", default="./references", help="download folder")
    ap.add_argument("--prefix", default="", help="file prefix (default: slug of the query)")
    ap.add_argument("--size", choices=["medium", "orig"], default="medium",
                    help="medium = web size (default, enough for reference); orig = full size")
    ap.add_argument("--sheet", action="store_true", help="also build a contact sheet (needs Pillow)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the table")
    a = ap.parse_args()

    names = list(SOURCES) if a.source.strip() == "all" else [s.strip() for s in a.source.split(",") if s.strip()]
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        sys.exit(f"unknown source(s): {', '.join(unknown)}; choose from {', '.join(SOURCES)} or all")

    per_source = []
    for n in names:
        try:
            items = SOURCES[n]().search(a.query, a.limit)
        except Exception as e:  # one broken site must not kill the others
            print(f"[{n}] failed: {e}", file=sys.stderr)
            items = []
        print(f"[{n}] {len(items)} results", file=sys.stderr)
        per_source.append(items)

    # interleave so a small --download still mixes sources
    items = []
    for k in range(max((len(x) for x in per_source), default=0)):
        for lst in per_source:
            if k < len(lst):
                items.append(lst[k])
    if not items:
        sys.exit("No references found. Try another phrasing, another --source, or the browser fallback.")

    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
    else:
        for i, p in enumerate(items):
            size = f"{p['width'] or '?'}x{p['height'] or '?'}"
            print(f"{i:>3}  {p['source']:<9} {size:>10} {p['color'] or '':8} {p['title'][:40]:<40} {p['image']}")

    idx = []
    if a.pick:
        idx = [int(x) for x in a.pick.split(",") if x.strip().isdigit()]
    elif a.download:
        idx = list(range(min(a.download, len(items))))
    idx = [i for i in idx if i < len(items)]
    if not idx:
        return

    os.makedirs(a.out, exist_ok=True)
    prefix = a.prefix or _slug(a.query)
    op = _opener()
    saved_idx, saved = [], []
    for i in idx:
        f = download(op, items[i], os.path.join(a.out, f"{prefix}-{i:02d}"), a.size)
        if f:
            saved_idx.append(i)
            saved.append(f)
    print("", file=sys.stderr)
    print("Downloaded:", file=sys.stderr)
    for f in saved:
        print(f)
    if saved:
        print(write_refs_md(a.query, items, saved_idx, saved, os.path.join(a.out, f"{prefix}-refs.md")))
        if a.sheet:
            sheet = contact_sheet(saved, os.path.join(a.out, f"{prefix}-sheet.jpg"))
            if sheet:
                print(sheet)


if __name__ == "__main__":
    main()
