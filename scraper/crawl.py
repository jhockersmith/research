#!/usr/bin/env python3
"""
Robots.txt-respecting, rate-limited crawler for public Palantir pages.

Scope discipline (see README.md "Legal/ToS boundary"):
  - only fetches URLs from seeds.SEED_URLS (no link-following/spidering)
  - checks robots.txt for each host before every fetch, refuses disallowed paths
  - single-threaded, 2s minimum gap between requests
  - identifies itself with a real User-Agent, no header spoofing

This is intentionally NOT a generic recursive scraper. It fetches a fixed,
human-curated URL list and extracts main text. Expanding coverage means adding
URLs to seeds.py, not adding crawl/link-follow logic.
"""
import argparse
import json
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from seeds import SEED_URLS

USER_AGENT = "PanderoseResearchBot/0.1 (+internal ontology research; contact: johnathanalonzo1@gmail.com)"
MIN_DELAY_SECONDS = 2.0
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
MANIFEST_PATH = DATA_DIR / "manifest.json"

_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def slugify(url: str) -> str:
    parsed = urlparse(url)
    slug = (parsed.netloc + parsed.path).strip("/")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()
    return slug or "index"


def allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(origin + "/robots.txt")
        try:
            rp.read()
        except Exception as e:
            print(f"  warning: could not read robots.txt for {origin}: {e}", file=sys.stderr)
            rp = None
        _robots_cache[origin] = rp
    rp = _robots_cache[origin]
    if rp is None:
        # robots.txt unreachable — fail closed, skip the page rather than assume allowed
        return False
    return rp.can_fetch(USER_AGENT, url)


PROSE_KEYS = {
    "text", "title", "heading", "subtitle", "subheading", "description",
    "body", "label", "summary", "caption", "content", "quote", "headline",
    "eyebrow", "name", "tagline",
}
SKIP_KEYS = {"sys", "contentType", "metadata", "url", "id", "openInNewTab"}


def _looks_like_prose(s: str) -> bool:
    if len(s) < 8 or " " not in s:
        return False
    if s.startswith(("http://", "https://", "/", "#")):
        return False
    return True


def extract_from_next_data(data) -> list[str]:
    """Recursively pull prose-looking strings out of a Next.js/Contentful JSON blob."""
    found: list[str] = []
    seen: set[str] = set()

    def walk(node, key_hint: str = ""):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in SKIP_KEYS:
                    continue
                walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key_hint)
        elif isinstance(node, str):
            if (key_hint in PROSE_KEYS or _looks_like_prose(node)) and _looks_like_prose(node):
                if node not in seen:
                    seen.add(node)
                    found.append(node)

    walk(data)
    return found


def extract_main_text(html: str) -> str:
    # Next.js/Contentful pages (palantir.com marketing site): real copy lives in
    # the __NEXT_DATA__ JSON blob, not in the server-rendered DOM.
    marker = "__NEXT_DATA__"
    idx = html.find(marker)
    if idx != -1:
        json_start = html.find(">", idx) + 1
        json_end = html.find("</script>", json_start)
        raw_json = html[json_start:json_end]
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            data = None
        if data is not None:
            strings = extract_from_next_data(data)
            if strings:
                return "\n".join(strings)

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def crawl(force: bool = False) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    for url in SEED_URLS:
        slug = slugify(url)
        out_path = DATA_DIR / f"{slug}.txt"

        if out_path.exists() and not force:
            print(f"skip (already fetched): {url}")
            continue

        if not allowed_by_robots(url):
            print(f"skip (robots.txt disallows): {url}")
            manifest[url] = {"status": "disallowed_by_robots", "slug": slug}
            continue

        try:
            resp = session.get(url, timeout=15)
        except requests.RequestException as e:
            print(f"error fetching {url}: {e}")
            manifest[url] = {"status": "error", "error": str(e), "slug": slug}
            time.sleep(MIN_DELAY_SECONDS)
            continue

        if resp.status_code == 200:
            text = extract_main_text(resp.text)
            # palantir.com is a Next.js SPA with a catch-all route: a missing page
            # still returns HTTP 200 with a "Page Not Found" soft-404 body.
            if "Page Not Found" in text[:800] or "Page not found" in text[:800]:
                manifest[url] = {"status": "soft_404", "slug": slug}
                print(f"soft 404 (skipped save): {url}")
                save_manifest(manifest)
                time.sleep(MIN_DELAY_SECONDS)
                continue
            out_path.write_text(text, encoding="utf-8")
            manifest[url] = {
                "status": "ok",
                "slug": slug,
                "chars": len(text),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            print(f"ok ({len(text)} chars): {url}")
        else:
            manifest[url] = {"status": f"http_{resp.status_code}", "slug": slug}
            print(f"http {resp.status_code}: {url}")

        save_manifest(manifest)
        time.sleep(MIN_DELAY_SECONDS)

    save_manifest(manifest)
    print(f"\nDone. {len(manifest)} URLs tracked in {MANIFEST_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-fetch even if already saved")
    args = parser.parse_args()
    crawl(force=args.force)
