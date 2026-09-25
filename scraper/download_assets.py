#!/usr/bin/env python3
"""
Download the images/diagrams referenced from already-crawled docs pages.

crawl_docs.py deliberately skips /docs/resources/... paths when discovering
pages (those are assets, not doc pages). This script does a separate pass:
scan every saved .md file under data/docs/ for /docs/resources/ references
and fetch each one, saved under data/docs_assets/ mirroring its path.

Same scope discipline as the other scripts: robots.txt checked, rate-limited,
identifiable User-Agent, resumable (skips files already downloaded).
"""
import json
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

USER_AGENT = "PanderoseResearchBot/0.1 (+internal ontology research; contact: johnathanalonzo1@gmail.com)"
MIN_DELAY_SECONDS = 0.5
BASE = "https://www.palantir.com"
DOCS_DIR = Path(__file__).parent.parent / "data" / "docs"
ASSETS_DIR = Path(__file__).parent.parent / "data" / "docs_assets"
MANIFEST_PATH = Path(__file__).parent.parent / "data" / "docs_assets_manifest.json"

ASSET_REF_RE = re.compile(r'(/docs/resources/[^)\s"\']+)')

_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


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
        return False
    return rp.can_fetch(USER_AGENT, url)


def find_asset_refs() -> set[str]:
    refs: set[str] = set()
    for md_file in DOCS_DIR.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        for match in ASSET_REF_RE.finditer(text):
            path = match.group(1).rstrip(").,")
            refs.add(path)
    return refs


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def download_assets() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    refs = sorted(find_asset_refs())
    print(f"Found {len(refs)} unique asset references across saved docs.")

    todo = [r for r in refs if r not in manifest]
    print(f"{len(todo)} not yet downloaded.")

    for i, path in enumerate(todo):
        url = BASE + path
        local_path = ASSETS_DIR / path[len("/docs/resources/"):]

        if not allowed_by_robots(url):
            manifest[path] = {"status": "disallowed_by_robots"}
            print(f"[{i+1}/{len(todo)}] skip (robots.txt disallows): {url}")
            continue

        try:
            resp = session.get(url, timeout=20)
        except requests.RequestException as e:
            manifest[path] = {"status": "error", "error": str(e)}
            print(f"[{i+1}/{len(todo)}] error fetching {url}: {e}")
            save_manifest(manifest)
            time.sleep(MIN_DELAY_SECONDS)
            continue

        if resp.status_code == 200:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(resp.content)
            manifest[path] = {
                "status": "ok",
                "file": str(local_path.relative_to(ASSETS_DIR.parent)),
                "bytes": len(resp.content),
                "content_type": resp.headers.get("Content-Type"),
            }
            print(f"[{i+1}/{len(todo)}] ok ({len(resp.content)} bytes): {url}")
        else:
            manifest[path] = {"status": f"http_{resp.status_code}"}
            print(f"[{i+1}/{len(todo)}] http {resp.status_code}: {url}")

        save_manifest(manifest)
        time.sleep(MIN_DELAY_SECONDS)

    save_manifest(manifest)
    ok = sum(1 for v in manifest.values() if v.get("status") == "ok")
    total_bytes = sum(v.get("bytes", 0) for v in manifest.values() if v.get("status") == "ok")
    print(f"\nDone. {len(manifest)} assets tracked, {ok} downloaded ({total_bytes/1024/1024:.1f} MB).")


if __name__ == "__main__":
    download_assets()
