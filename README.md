# Palantir Capability Ontology Research

Goal: extract Palantir's publicly documented technical capabilities (Foundry, AIP,
Gotham, Apollo, Ontology/data-integration patterns) and generalize them into an
industry-agnostic capability ontology — reference material for Panderose's own
[[panderose-context-server]] / Locus-based ontology work (see project memory).

## Why generalized, not copied

Palantir's pitch isn't really "we have 50 products for 50 industries" — it's a small
set of **generic primitives** (a live object model over federated data, a pipeline/
lineage layer, an operational write-back layer, an AI-action layer with human
approval gates) that get *re-skinned* per industry. The value of this research is
capturing those primitives abstractly enough to apply to Panderose/Clerid, not
copying Palantir's product surface.

## Legal/ToS boundary — read before extending the scraper

Palantir's docs site and product pages carry standard ToS restricting automated
bulk scraping. This project only crawls pages that are:
- publicly reachable without login,
- allowed by `robots.txt` at fetch time,
- fetched at a conservative rate (1 request / 2s, single-threaded, identifiable
  User-Agent).

It does **not** attempt to bypass logins, paywalls, or `robots.txt` disallow rules.
Gated technical docs (the actual Foundry/AIP developer docs behind an account) are
explicitly out of scope for the automated crawler — if you have legitimate access
and want that material included, extract it manually (browser pane, copy relevant
sections) and drop the text into `data/raw/manual/`.

## Structure

- `scraper/crawl.py` — robots.txt-respecting, rate-limited crawler for a fixed seed
  list of public marketing/product pages. Saves cleaned page text to
  `data/raw/<slug>.txt` + `data/raw/manifest.json`.
- `scraper/seeds.py` — the seed URL list for `crawl.py` (public product/docs/
  case-study pages only).
- `scraper/crawl_docs.py` — a BFS spider over the full public `palantir.com/docs`
  tree (justified there because robots.txt is `Allow: /` and there's a dedicated
  `/docs/sitemap.xml`). Discovers pages via each doc page's embedded nav tree and
  in-content links; saves each page's actual markdown source to `data/docs/`,
  mirroring the URL path. Resumable — persists `data/docs_frontier.json` and
  `data/docs_manifest.json` so an interrupted run picks back up.
- `scraper/download_assets.py` — separate pass that scans saved `.md` files for
  `/docs/resources/...` image references and downloads them. **Not committed to
  this repo** — see note below.
- `data/raw/` — extracted raw text from the marketing-site crawl.
- `data/docs/` — the full mirrored `palantir.com/docs` tree as markdown, ~3,555
  pages / ~21MB across Foundry, Gotham, Apollo, and Defense-OSDK.
- `ontology/capability_ontology.yaml` — the generalized, industry-agnostic capability
  ontology (the actual deliverable). 11 primitives (semantic data layer, entity
  resolution, dynamic logic layer, kinetic action layer, scenario simulation,
  governance guardrails, pipeline lineage, tool factory, vector/semantic search,
  feedback-driven AI ops, application layer), each evidence-cited back to a
  specific fetched page, plus cross-industry examples showing the same primitives
  re-skinned per vertical.
- `ontology/schema.md` — describes the ontology's field meanings, meant to be stable
  enough that Locus/the context server can ingest this file directly later.

## Images are intentionally not in this repo

The docs crawl also pulled every referenced diagram/screenshot (~7,400 files,
~2.1GB) via `download_assets.py`. That set is kept local-only
(`data/docs_assets/`, gitignored) — too large for a git repo and not needed for
the text-based ontology work. Re-run `python scraper/download_assets.py` after
`crawl_docs.py` on any checkout to regenerate it locally if needed.

## Running the crawlers

```bash
python scraper/crawl.py            # marketing site, fixed seed list
python scraper/crawl_docs.py       # full docs tree, resumable BFS spider
python scraper/download_assets.py  # images referenced from data/docs/ (local only)
```

## Status

Both crawls are complete as of 2026-09-24: marketing site (~20 offering/platform
pages) and the full public docs tree (3,555 pages saved, 0 remaining in the
crawl frontier). The capability ontology has been used once already to compare
against Panderose's own Cambium Ontology Platform and propose a generalized
capability roadmap for it — see project memory / the Cambium design artifact
for that comparison.
