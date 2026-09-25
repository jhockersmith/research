#!/usr/bin/env python3
"""
Full mirror of the public English palantir.com/docs tree.

Unlike crawl.py (a fixed seed list for the marketing site), this is a BFS
spider — justified here because:
  - robots.txt for palantir.com is `Allow: /` (verified at run time, not
    hard-coded) and there is a dedicated /docs/sitemap.xml, so the docs tree
    is meant to be crawled.
  - Each doc page's Next.js __NEXT_DATA__ blob embeds the page's actual
    markdown source (pageProps.markdown) plus a full sidebar nav tree
    (pageProps.sidebarNavProps) listing every other page in that section —
    that's the discovery mechanism, not generic link-following across the
    whole site.

Scope discipline:
  - stays on palantir.com / www.palantir.com, path prefix /docs/ only
  - English only: never follows a link into a known locale-prefixed subtree
    (/docs/jp/, /docs/kr/, /docs/zh/, /docs/fr/, /docs/de/, ...)
  - does not follow asset links (/docs/resources/...) or off-site links
  - single-threaded, rate-limited, identifiable User-Agent, robots.txt checked
    per host before the first request (same helper as crawl.py)
"""
import argparse
import json
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests

USER_AGENT = "PanderoseResearchBot/0.1 (+internal ontology research; contact: johnathanalonzo1@gmail.com)"
MIN_DELAY_SECONDS = 1.0
BASE = "https://www.palantir.com"
DOCS_PREFIX = "/docs/"
OUT_DIR = Path(__file__).parent.parent / "data" / "docs"
MANIFEST_PATH = Path(__file__).parent.parent / "data" / "docs_manifest.json"
FRONTIER_PATH = Path(__file__).parent.parent / "data" / "docs_frontier.json"

LOCALE_PREFIXES = {"jp", "kr", "zh", "fr", "de", "es", "it", "pt"}

# Only these first-path-segments under /docs/ are real product doc namespaces
# (confirmed against /docs/sitemap.xml). Everything else reachable via a
# relative nav href (e.g. "/offerings/utilities/") is a link to the main
# marketing site, not a docs page — the marketing site was already covered by
# crawl.py, so we drop those here rather than chase 404s under a wrong /docs/
# prefix.
ALLOWED_PRODUCTS = {"foundry", "gotham", "apollo", "defense-osdk"}

SEEDS = [
    "/docs/",
    "/docs/foundry/",
    "/docs/foundry/announcements/release-notes/",
    "/docs/foundry/api-reference/",
    "/docs/gotham/",
    "/docs/apollo/",
    "/docs/defense-osdk/",
]

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


def normalize_link(raw: str, current_url: str) -> str | None:
    """Resolve a link found in nav JSON or markdown into a canonical /docs/ URL,
    or None if it's out of scope (asset, external, non-English locale, etc.)."""
    if not raw or raw.startswith(("http://", "https://", "mailto:", "#", "javascript:")):
        # allow absolute palantir.com links through the scope filter below
        if raw.startswith(("http://", "https://")) and "palantir.com" not in raw:
            return None
        if raw.startswith(("mailto:", "#", "javascript:")):
            return None

    path = raw
    if path.startswith("http"):
        path = urlparse(path).path

    if not path.startswith("/"):
        path = urljoin(current_url, path)
        path = urlparse(path).path

    # sidebarNavProps links omit the /docs prefix (e.g. "/foundry/x/"); markdown
    # content links include it (e.g. "/docs/foundry/x/"). Normalize both.
    if not path.startswith(DOCS_PREFIX):
        path = DOCS_PREFIX + path.lstrip("/")

    # strip query/fragment for dedup purposes
    path = path.split("?")[0].split("#")[0]
    if not path.endswith("/"):
        path = path + "/"

    rest = path[len(DOCS_PREFIX):]
    first_segment = rest.split("/")[0]
    if first_segment in LOCALE_PREFIXES:
        return None
    if first_segment == "resources":
        return None  # images/assets, not pages
    if rest and first_segment not in ALLOWED_PRODUCTS:
        return None  # not a real docs namespace (see ALLOWED_PRODUCTS comment)

    return BASE + path


def url_to_filepath(url: str) -> Path:
    path = urlparse(url).path  # e.g. /docs/foundry/ontology/overview/
    rest = path[len(DOCS_PREFIX):].strip("/")
    if not rest:
        rest = "index"
    return OUT_DIR / (rest + ".md")


LINKISH_KEYS = {"url", "href", "link"}


def collect_links_from_json(node, current_url: str, out: set[str], key_hint: str = "") -> None:
    """Generic recursive harvest: any string value that looks like a site-relative
    path, anywhere in the pageProps tree (sidebarNavProps, docsHomepageConfig's
    teaserCards/referenceCells, pageNeighbours, breadcrumbs, ...). Landing pages
    and content pages use different JSON shapes, so this doesn't special-case
    any one of them — it just walks everything."""
    if isinstance(node, dict):
        for k, v in node.items():
            collect_links_from_json(v, current_url, out, key_hint=k)
    elif isinstance(node, list):
        for item in node:
            collect_links_from_json(item, current_url, out, key_hint=key_hint)
    elif isinstance(node, str):
        if node.startswith("/") or (key_hint in LINKISH_KEYS and "palantir.com" in node):
            norm = normalize_link(node, current_url)
            if norm:
                out.add(norm)


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def collect_links_from_markdown(markdown: str, current_url: str, out: set[str]) -> None:
    for match in MARKDOWN_LINK_RE.finditer(markdown):
        norm = normalize_link(match.group(1), current_url)
        if norm:
            out.add(norm)


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def fetch_page(session: requests.Session, url: str) -> tuple[str | None, set[str], dict | None]:
    """Returns (markdown_or_None, discovered_links, metadata_or_None)."""
    try:
        resp = session.get(url, timeout=20)
    except requests.RequestException as e:
        print(f"  error: {e}")
        return None, set(), None

    if resp.status_code != 200:
        print(f"  http {resp.status_code}")
        return None, set(), None

    html = resp.text
    idx = html.find("__NEXT_DATA__")
    if idx == -1:
        return None, set(), None
    json_start = html.find(">", idx) + 1
    json_end = html.find("</script>", json_start)
    try:
        data = json.loads(html[json_start:json_end])
    except json.JSONDecodeError:
        return None, set(), None

    pp = data.get("props", {}).get("pageProps", {})
    markdown = pp.get("markdown")
    links: set[str] = set()
    collect_links_from_json(pp, url, links)
    if isinstance(markdown, str):
        collect_links_from_markdown(markdown, url, links)

    metadata = {
        "title": (pp.get("metadata") or {}).get("title") if isinstance(pp.get("metadata"), dict) else None,
        "pageId": pp.get("pageId"),
        "categoryId": pp.get("categoryId"),
        "sectionId": pp.get("sectionId"),
        "productId": pp.get("productId"),
    }
    return (markdown if isinstance(markdown, str) else None), links, metadata


def load_frontier() -> list[str]:
    if FRONTIER_PATH.exists():
        return json.loads(FRONTIER_PATH.read_text(encoding="utf-8"))
    return []


def save_frontier(queue: list[str]) -> None:
    FRONTIER_PATH.write_text(json.dumps(queue), encoding="utf-8")


def crawl(max_pages: int | None = None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    visited: set[str] = set(manifest.keys())
    saved_frontier = [u for u in load_frontier() if u not in visited]
    seeds = [BASE + s for s in SEEDS if (BASE + s) not in visited]
    # de-dupe while preserving order: resume frontier first, then any new seeds
    queue: list[str] = []
    seen_in_queue: set[str] = set()
    for u in saved_frontier + seeds:
        if u not in seen_in_queue:
            queue.append(u)
            seen_in_queue.add(u)
    queued: set[str] = set(queue)
    fetched_count = 0
    print(f"Resuming: {len(visited)} already visited, {len(queue)} in frontier.")

    while queue:
        if max_pages is not None and fetched_count >= max_pages:
            print(f"Reached max_pages={max_pages}, stopping (queue still has {len(queue)} URLs).")
            break

        url = queue.pop(0)
        if url in visited:
            continue

        if not allowed_by_robots(url):
            print(f"skip (robots.txt disallows): {url}")
            visited.add(url)
            continue

        print(f"[{len(visited)+1} visited, {len(queue)} queued] fetching {url}")
        markdown, links, metadata = fetch_page(session, url)
        visited.add(url)
        fetched_count += 1

        if markdown is not None:
            filepath = url_to_filepath(url)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            title = (metadata or {}).get("title") or ""
            header = f"---\nurl: {url}\ntitle: {title}\nfetched_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n---\n\n"
            filepath.write_text(header + markdown, encoding="utf-8")
            manifest[url] = {
                "status": "ok",
                "file": str(filepath.relative_to(OUT_DIR.parent)),
                "title": title,
                "chars": len(markdown),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            print(f"  saved ({len(markdown)} chars) -> {filepath.name}")
        else:
            manifest[url] = {"status": "no_markdown"}
            print("  no markdown content on this page (nav/index page or fetch failed)")

        for link in links:
            if link not in visited and link not in queued:
                queue.append(link)
                queued.add(link)

        save_manifest(manifest)
        save_frontier(queue)
        time.sleep(MIN_DELAY_SECONDS)

    save_manifest(manifest)
    save_frontier(queue)
    ok_count = sum(1 for v in manifest.values() if v.get("status") == "ok")
    print(f"\nDone. {len(manifest)} URLs tracked, {ok_count} pages saved with content, in {MANIFEST_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=None, help="stop after fetching this many new pages (for testing)")
    args = parser.parse_args()
    crawl(max_pages=args.max_pages)
