#!/usr/bin/env python3
"""Search visual references across design sites (no login; API keys only for the optional
photo sources), list them, download them, and build a numbered contact sheet.

Usage:
  python3 sauce.py "brutalist poster"                               # Pinterest (default)
  python3 sauce.py "brutalist poster" --source all --limit 6        # every keyless source, 6 each
  python3 sauce.py "fintech dashboard" --source dribbble,cosmos,awwwards --download 12 --sheet
  python3 sauce.py "japandi living room" --source pinterest,archdaily --pick 2,5,11 --size orig
  python3 sauce.py --sources                                        # list sources and what they are good for

Sources (script): pinterest, dribbble, cosmos, designspiration, fontsinuse, awwwards,
landbook, dieline, archdaily, met. With an API key in the environment: unsplash
(UNSPLASH_ACCESS_KEY), pexels (PEXELS_API_KEY). Behance, Mobbin, ArtStation and the Art
Institute of Chicago block scripts: use scripts/browser_extract.js in a browser instead.

Default output: one line per reference -> index, source, width x height, dominant color,
title, image URL. Downloads also produce <slug>-refs.md (table of the saved references with
page links and authors when the source provides them) and, with --sheet and Pillow
installed, <slug>-sheet.jpg (numbered contact sheet).

Every keyless source uses the public endpoint the site's own logged-out page calls; any of
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
API_UA = "sauce-skill/1.0 (+https://github.com/carloshernanic/sauce)"


def _read(resp):
    body = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)
    return body


class Http:
    def __init__(self, ua=UA):
        self.jar = CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.op.addheaders = [("User-Agent", ua), ("Accept-Language", "en-US,en;q=0.9")]

    def get(self, url, headers=None, data=None, timeout=30):
        req = urllib.request.Request(url, data=data, headers=headers or {})
        return _read(self.op.open(req, timeout=timeout))

    def text(self, url, headers=None):
        h = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
        h.update(headers or {})
        return self.get(url, h).decode("utf-8", "ignore")

    def json(self, url, headers=None, data=None):
        h = {"Accept": "application/json"}
        h.update(headers or {})
        return json.loads(self.get(url, h, data))

    def cookie(self, name):
        return next((c.value for c in self.jar if c.name == name), "")


def _slug(text, n=40):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:n]


def _q(text):
    return urllib.parse.quote(text)


def _clean(s):
    return html.unescape(re.sub(r"\s+", " ", s or "")).strip()


def query_variants(query):
    """Some searches return nothing for an exact phrasing; try natural variants."""
    words = query.split()
    yield query
    yield query + " design inspiration"
    yield query + " ideas"
    if len(words) > 2:
        yield " ".join(words[:-1])
        yield " ".join(words[1:])


def ref(source, id, image, medium=None, width=None, height=None, color=None,
        title="", author="", page=""):
    return {"source": source, "id": str(id), "title": _clean(title)[:140],
            "author": _clean(author)[:80], "page": page or "",
            "width": width, "height": height, "color": color,
            "image": image, "medium": medium or image}


class Source:
    name = ""
    about = ""
    needs_key = None

    def __init__(self):
        self.http = Http()

    def search(self, query, limit):
        raise NotImplementedError


# --------------------------------------------------------------------------- Pinterest
class Pinterest(Source):
    name = "pinterest"
    about = "anything visual: illustration, photo, interiors, fashion, posters, mood"
    BASE = "https://www.pinterest.com"

    def __init__(self):
        super().__init__()
        page = self.http.text(self.BASE + "/")
        m = re.search(r'"appVersion":"([0-9a-f]+)"', page)
        self.app_version = m.group(1) if m else ""
        self.csrf = self.http.cookie("csrftoken")

    def _page(self, query, bookmark=None, page_size=25):
        src = "/search/pins/?q=" + _q(query)
        data = json.dumps({"options": {"query": query, "scope": "pins",
                                       "bookmarks": [bookmark] if bookmark else [],
                                       "page_size": page_size, "redux_normalize_feed": True,
                                       "rs": "typed", "source_url": src},
                           "context": {}})
        url = self.BASE + "/resource/BaseSearchResource/get/?" + urllib.parse.urlencode(
            {"source_url": src, "data": data, "_": str(int(time.time() * 1000))})
        rr = self.http.json(url, {
            "Accept": "application/json, text/javascript, */*, q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "X-Pinterest-AppState": "active",
            "X-APP-VERSION": self.app_version,
            "X-CSRFToken": self.csrf,
            # These two headers are what distinguishes an accepted request from a 403.
            "x-pinterest-source-url": src,
            "x-pinterest-pws-handler": "www/search/[scope].js",
            "Referer": self.BASE + src,
        })["resource_response"]
        out = []
        for p in rr.get("data", {}).get("results", []):
            if p.get("type") != "pin" or "images" not in p:
                continue
            orig = p["images"].get("orig") or {}
            mid = p["images"].get("736x") or orig
            out.append(ref(self.name, p.get("image_signature") or p.get("id"),
                           orig.get("url"), mid.get("url"), orig.get("width"), orig.get("height"),
                           p.get("dominant_color")))
        return out, rr.get("bookmark")

    def search(self, query, limit):
        for q in query_variants(query):
            out, seen, bm = [], set(), None
            for _ in range(10):
                pins, bm = self._page(q, bm)
                for p in pins:
                    if p["id"] not in seen:
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
class Dribbble(Source):
    name = "dribbble"
    about = "UI, app screens, icons, branding, motion stills"
    BASE = "https://dribbble.com"

    def _page(self, query, page):
        text = self.http.text(f"{self.BASE}/search/{_slug(query, 80)}?page={page}&per_page=24",
                              {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
        out = []
        for m in re.finditer(r'<li\s+id="screenshot-(\d+)"(.*?)</li>', text, re.S):
            sid, card = m.group(1), m.group(2)
            base = re.search(r'(https://cdn\.dribbble\.com/userupload/[^"?\s]+\.(?:png|jpe?g|gif|webp))', card, re.I)
            if not base:  # video-only shots have no still we can use
                continue
            base = html.unescape(base.group(1))
            title = re.search(r'class="shot-title">\s*(.*?)\s*<', card, re.S)
            color = re.search(r'background-color:\s*(#[0-9a-fA-F]{6})', card)
            author = re.search(r'class="display-name">\s*(.*?)\s*<', card, re.S)
            link = re.search(r'href="(/shots/[^"]+)"', card)
            out.append(ref(self.name, sid, base, base + "?format=webp&resize=1200x900&vertical=center",
                           None, None, color.group(1).lower() if color else None,
                           title.group(1) if title else "", author.group(1) if author else "",
                           self.BASE + link.group(1) if link else ""))
        return out

    def search(self, query, limit):
        out, seen = [], set()
        for page in range(1, 6):
            items = self._page(query, page)
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
class Cosmos(Source):
    """cosmos.so: search returns curated collections ("clusters"); we then pull the
    elements of the best-matching collections."""
    name = "cosmos"
    about = "curated, high-taste collections: art direction, editorial, photography, type"
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

    def _gql(self, op, query, variables):
        body = json.dumps({"operationName": op, "query": query, "variables": variables}).encode()
        j = self.http.json(self.API, {"Content-Type": "application/json", "Origin": "https://www.cosmos.so",
                                      "Referer": "https://www.cosmos.so/explore"}, body)
        if j.get("errors"):
            raise RuntimeError(j["errors"][0].get("message"))
        return j["data"]

    def _clusters(self, query):
        words = query.split()
        variants = [query] + ([" ".join(words[:-1]), " ".join(words[1:])] if len(words) > 2 else []) \
            + ([" ".join(words[:2])] if len(words) > 3 else []) + [query + " design"]
        tried = []
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
        clusters = sorted(self._clusters(query), key=lambda c: -(c.get("numberOfElements") or 0))
        out, seen = [], set()
        for c in clusters[:4]:
            cursor = None
            while len(out) < limit:
                page = self._gql("GetClusterElements", self.Q_ELEMENTS,
                                 {"clusterId": c["id"], "pageSize": 24, "pageCursor": cursor})["clusterConnections"]
                for it in page["items"]:
                    e = it["element"]
                    media = e.get("media") or {}
                    if not media.get("url") or media.get("__typename") not in ("StaticImage", None) or e["id"] in seen:
                        continue
                    seen.add(e["id"])
                    cap = re.sub(r"</?n>", "", (e.get("generatedCaption") or {}).get("text") or "")
                    src = e.get("source") or {}
                    author = (src.get("author") or {}).get("username") or (e.get("owner") or {}).get("username") or ""
                    out.append(ref(self.name, e["id"], media["url"], media["url"], media.get("width"), media.get("height"),
                                   None, cap[:120] or f"from collection '{c['name']}'", author, e.get("shareUrl") or ""))
                    if len(out) >= limit:
                        break
                cursor = (page.get("meta") or {}).get("nextPageCursor")
                if not cursor:
                    break
            if len(out) >= limit:
                break
        return out[:limit]


# --------------------------------------------------------------------------- Designspiration
class Designspiration(Source):
    name = "designspiration"
    about = "graphic design, identity, print, typography, with a 5-color palette per item"
    BASE = "https://www.designspiration.com"

    def search(self, query, limit):
        out, seen = [], set()
        for page in range(1, 5):
            text = self.http.text(f"{self.BASE}/search/saves/?q={_q(query)}&page={page}")
            m = re.search(r'<script type="application/json" id="PJSD">(.*?)</script>', text, re.S)
            if not m:
                break
            items = json.loads(m.group(1)).get("data") or []
            if not items:
                break
            for d in items:
                if d.get("id") in seen or d.get("media_type") not in (None, "image"):
                    continue
                seen.add(d["id"])
                imgs = d.get("images") or {}
                big = imgs.get("4x") or imgs.get("3x") or imgs.get("2x") or imgs.get("1x") or {}
                mid = imgs.get("3x") or imgs.get("2x") or big
                palette = d.get("palette") or []
                out.append(ref(self.name, d["id"], big.get("url"), mid.get("url"), None, None,
                               palette[0] if palette else None,
                               d.get("title") or d.get("description") or "", d.get("user_display_name") or "",
                               f"{self.BASE}/save/{d['id']}/"))
            if len(out) >= limit:
                break
        return out[:limit]


# --------------------------------------------------------------------------- Fonts In Use
class FontsInUse(Source):
    name = "fontsinuse"
    about = "typography in real use: posters, books, identities, packaging, signage"
    BASE = "https://fontsinuse.com"

    def search(self, query, limit):
        text = self.http.text(f"{self.BASE}/search?terms={_q(query)}")
        out, seen = [], set()
        for m in re.finditer(r'<div class="fiu-galleryItem"[^>]*data-id="(\d+)"[^>]*>(.*?)</picture>', text, re.S):
            sid, card = m.group(1), m.group(2)
            link = re.search(r'href="(/uses/[^"]+)"', card)
            if not link or sid in seen:
                continue
            seen.add(sid)
            title = re.search(r'fiu-galleryItem__headline">(.*?)</span>', card, re.S)
            designers = re.findall(r'fiu-galleryItem__designers">\s*<li>(.*?)</li>', card, re.S)
            img = re.search(r'<img[^>]*src="([^"]+)"', card)
            img2 = re.search(r'(https://assets\.fontsinuse\.com/\S*@2x/\S+?\.(?:webp|jpe?g|png))', card)
            if not img:
                continue
            out.append(ref(self.name, sid, (img2.group(1) if img2 else img.group(1)), img.group(1), None, None, None,
                           title.group(1) if title else "", designers[0] if designers else "",
                           self.BASE + link.group(1)))
            if len(out) >= limit:
                break
        return out


# --------------------------------------------------------------------------- Awwwards
class Awwwards(Source):
    name = "awwwards"
    about = "award-level websites and landing pages, full-page screenshots"
    BASE = "https://www.awwwards.com"

    def search(self, query, limit):
        out, seen = [], set()
        for page in range(1, 4):
            text = self.http.text(f"{self.BASE}/websites/?text={_q(query)}&page={page}")
            found = 0
            # the anchor's data-action attribute contains "->", so do not stop at the first ">"
            for m in re.finditer(r'<a aria-label="([^"]*)" class="figure-rollover__link" href="(/sites/[^"]+)".*?<img.*?data-srcset="([^"]+)"', text, re.S):
                title, link, srcset = m.groups()
                if link in seen:
                    continue
                seen.add(link)
                found += 1
                urls = [s.strip().split(" ")[0] for s in html.unescape(srcset).split(",")]
                out.append(ref(self.name, link.rsplit("/", 1)[-1], urls[-1], urls[0], None, None, None,
                               title, "", self.BASE + link))
                if len(out) >= limit:
                    return out
            if not found:
                break
        return out


# --------------------------------------------------------------------------- Land-book
class Landbook(Source):
    name = "landbook"
    about = "landing pages and marketing sites, curated, full-page screenshots"
    BASE = "https://land-book.com"

    def search(self, query, limit):
        out, seen = [], set()
        for page in range(1, 4):
            text = self.http.text(f"{self.BASE}/?search={_q(query)}&page={page}")
            found = 0
            for m in re.finditer(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', text, re.S):
                try:
                    j = json.loads(m.group(1))
                except ValueError:
                    continue
                for el in j.get("itemListElement") or []:
                    it = el.get("item") or {}
                    url, img = it.get("url"), it.get("image")
                    if not url or not img or url in seen or "/websites/" not in url:
                        continue
                    seen.add(url)
                    found += 1
                    out.append(ref(self.name, url.rsplit("/", 1)[-1].split("-")[0], img,
                                   re.sub(r"/1200x0/", "/800x0/", img), None, None, None, it.get("name") or "", "", url))
                    if len(out) >= limit:
                        return out
            if not found:
                break
        return out


# --------------------------------------------------------------------------- The Dieline
class Dieline(Source):
    name = "dieline"
    about = "packaging design and branding case studies"
    BASE = "https://thedieline.com"

    def search(self, query, limit):
        text = self.http.text(f"{self.BASE}/search?q={_q(query)}")
        out, seen = [], set()
        for m in re.finditer(r'<figure class="wp-block-post-featured-image"><a href="([^"]+)"[^>]*>\s*<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"', text, re.S):
            url, img, title = m.groups()
            if url in seen:
                continue
            seen.add(url)
            img = html.unescape(img)
            out.append(ref(self.name, url.rstrip("/").rsplit("/", 1)[-1][:40], img,
                           re.sub(r"-scaled(-\d+)?\.", r"-1024x683.", img) if "-scaled" in img else img,
                           None, None, None, title, "", url))
            if len(out) >= limit:
                break
        return out


# --------------------------------------------------------------------------- ArchDaily
class ArchDaily(Source):
    name = "archdaily"
    about = "architecture and interiors projects with professional photography"
    API = "https://www.archdaily.com/search/api/v1/us/projects"

    def search(self, query, limit):
        out, seen = [], set()
        for page in range(1, 4):
            j = self.http.json(f"{self.API}?q={_q(query)}&page={page}")
            results = j.get("results") or []
            if not results:
                break
            for r in results:
                fi = r.get("featured_images") or {}
                img = fi.get("url_large") or fi.get("url_medium")
                if not img or r.get("document_id") in seen:
                    continue
                seen.add(r["document_id"])
                title = r.get("title") or ""
                if r.get("year"):
                    title += f" ({r['year']})"
                office = ", ".join(o.get("name", "") for o in (r.get("offices") or []) if o.get("name"))
                out.append(ref(self.name, r["document_id"], img, fi.get("url_medium") or img, None, None, None,
                               title, office or (r.get("author") or {}).get("name", ""), r.get("url") or ""))
                if len(out) >= limit:
                    return out
        return out


# --------------------------------------------------------------------------- The Met
class Met(Source):
    name = "met"
    about = "The Met's open-access collection: paintings, prints, posters, textiles, objects (public domain)"
    API = "https://collectionapi.metmuseum.org/public/collection/v1"

    def __init__(self):
        super().__init__()
        self.http = Http(API_UA)

    def search(self, query, limit):
        j = self.http.json(f"{self.API}.1/search?q={_q(query)}&hasImages=true&isPublicDomain=true")
        ids = j.get("objectIDs") or []
        out = []
        for oid in ids[:min(limit * 8, 80)]:  # many hits carry no public image; scan a few extra
            try:
                o = self.http.json(f"{self.API}/objects/{oid}")
            except Exception:
                continue
            img = o.get("primaryImage")
            if not img:
                continue
            title = o.get("title") or ""
            if o.get("objectDate"):
                title += f" ({o['objectDate']})"
            out.append(ref(self.name, oid, img, o.get("primaryImageSmall") or img, None, None, None,
                           title, o.get("artistDisplayName") or "", o.get("objectURL") or ""))
            if len(out) >= limit:
                break
        return out


# --------------------------------------------------------------------------- Unsplash / Pexels (keys)
class Unsplash(Source):
    name = "unsplash"
    about = "photography (free license); needs UNSPLASH_ACCESS_KEY"
    needs_key = "UNSPLASH_ACCESS_KEY"

    def search(self, query, limit):
        key = os.environ.get(self.needs_key)
        if not key:
            raise RuntimeError(f"set {self.needs_key} (free at unsplash.com/developers)")
        out = []
        for page in range(1, 4):
            j = self.http.json(f"https://api.unsplash.com/search/photos?query={_q(query)}&per_page=30&page={page}",
                               {"Authorization": "Client-ID " + key, "Accept-Version": "v1"})
            for p in j.get("results") or []:
                u = p.get("urls") or {}
                out.append(ref(self.name, p["id"], u.get("full") or u.get("raw"), u.get("regular"),
                               p.get("width"), p.get("height"), p.get("color"),
                               p.get("alt_description") or p.get("description") or "",
                               (p.get("user") or {}).get("name", ""), (p.get("links") or {}).get("html", "")))
                if len(out) >= limit:
                    return out
            if page >= (j.get("total_pages") or 1):
                break
        return out


class Pexels(Source):
    name = "pexels"
    about = "photography (free license); needs PEXELS_API_KEY"
    needs_key = "PEXELS_API_KEY"

    def search(self, query, limit):
        key = os.environ.get(self.needs_key)
        if not key:
            raise RuntimeError(f"set {self.needs_key} (free at pexels.com/api)")
        out = []
        for page in range(1, 4):
            j = self.http.json(f"https://api.pexels.com/v1/search?query={_q(query)}&per_page=40&page={page}",
                               {"Authorization": key})
            for p in j.get("photos") or []:
                s = p.get("src") or {}
                out.append(ref(self.name, p["id"], s.get("original"), s.get("large2x") or s.get("large"),
                               p.get("width"), p.get("height"), p.get("avg_color"), p.get("alt") or "",
                               p.get("photographer") or "", p.get("url") or ""))
                if len(out) >= limit:
                    return out
            if not j.get("next_page"):
                break
        return out


SOURCES = {cls.name: cls for cls in (Pinterest, Dribbble, Cosmos, Designspiration, FontsInUse, Awwwards,
                                     Landbook, Dieline, ArchDaily, Met, Unsplash, Pexels)}
KEYLESS = [n for n, c in SOURCES.items() if not c.needs_key]
BROWSER_ONLY = {"behance": "full case studies: branding, identity, packaging, editorial, 3D",
                "mobbin": "real app screenshots and flows (needs your own login)",
                "artstation": "concept art, game art, 3D, illustration",
                "artic": "Art Institute of Chicago open-access collection"}


# --------------------------------------------------------------------------- download & output
def download(http, item, path, size="medium"):
    urls = (item["image"], item["medium"]) if size == "orig" else (item["medium"], item["image"])
    for url in urls:
        if not url:
            continue
        try:
            host = urllib.parse.urlparse(url).netloc
            resp = http.op.open(urllib.request.Request(url, headers={"Referer": f"https://{host}/"}), timeout=60)
            body = _read(resp)
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0]
            ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
                   "image/avif": ".avif"}.get(ctype) or os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".jpg"
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
    ap.add_argument("query", nargs="?")
    ap.add_argument("--source", default="pinterest",
                    help="comma-separated source names, or 'all' for every keyless source (default: pinterest)")
    ap.add_argument("--sources", action="store_true", help="list sources and exit")
    ap.add_argument("--limit", type=int, default=30, help="how many references per source")
    ap.add_argument("--download", type=int, default=0, help="download the first N references (sources interleaved)")
    ap.add_argument("--pick", default="", help="download only these indexes, e.g. 2,5,11")
    ap.add_argument("--out", default="./references", help="download folder")
    ap.add_argument("--prefix", default="", help="file prefix (default: slug of the query)")
    ap.add_argument("--size", choices=["medium", "orig"], default="medium",
                    help="medium = web size (default, enough for reference); orig = full size")
    ap.add_argument("--sheet", action="store_true", help="also build a contact sheet (needs Pillow)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the table")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):  # titles carry accents; Windows consoles default to cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if a.sources or not a.query:
        print("script sources:")
        for n, c in SOURCES.items():
            print(f"  {n:<16} {c.about}" + (f"  [env {c.needs_key}]" if c.needs_key else ""))
        print("browser only (scripts/browser_extract.js):")
        for n, about in BROWSER_ONLY.items():
            print(f"  {n:<16} {about}")
        return

    names = KEYLESS if a.source.strip() == "all" else [s.strip() for s in a.source.split(",") if s.strip()]
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        sys.exit(f"unknown source(s): {', '.join(unknown)}; run --sources to list them")

    per_source = []
    for n in names:
        try:
            items = SOURCES[n]().search(a.query, a.limit)
        except Exception as e:  # one broken site must not kill the others
            print(f"[{n}] failed: {e}", file=sys.stderr)
            items = []
        print(f"[{n}] {len(items)} results", file=sys.stderr)
        per_source.append(items)

    items = []  # interleave so a small --download still mixes sources
    for k in range(max((len(x) for x in per_source), default=0)):
        for lst in per_source:
            if k < len(lst):
                items.append(lst[k])
    if not items:
        sys.exit("No references found. Try another phrasing, another --source, or the browser extractor.")

    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=1))
    else:
        for i, p in enumerate(items):
            size = f"{p['width'] or '?'}x{p['height'] or '?'}"
            print(f"{i:>3}  {p['source']:<15} {size:>10} {p['color'] or '':8} {p['title'][:40]:<40} {p['image']}")

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
    http = Http()
    saved_idx, saved = [], []
    for i in idx:
        f = download(http, items[i], os.path.join(a.out, f"{prefix}-{i:02d}"), a.size)
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
