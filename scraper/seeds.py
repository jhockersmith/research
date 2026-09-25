"""
Seed URLs for the crawler.

Only include URLs that are publicly reachable without login. If you find a page
requires auth, move it to the "gated / manual only" list at the bottom as a note
for manual extraction instead of adding it here.
"""

SEED_URLS = [
    # Corporate / product overview
    "https://www.palantir.com/",
    "https://www.palantir.com/platforms/foundry/",
    "https://www.palantir.com/platforms/aip/",
    "https://www.palantir.com/platforms/gotham/",
    "https://www.palantir.com/platforms/apollo/",
    # "mesa" and "what-we-do" are soft-404s on the current site (checked via
    # /sitemap.xml) — left out. blog.palantir.com disallows crawling in robots.txt.
    # Public docs landing page (top-level only — do not crawl into gated app docs;
    # /docs/foundry/getting-started|ontology|aip overview paths are also soft-404s
    # currently, likely renamed/gated — re-check sitemap.xml if resuming this).
    "https://www.palantir.com/docs/foundry/",
    # Industry/offering pages (this is where "generalizes to every industry" evidence
    # lives) — real slugs confirmed against /sitemap.xml, not guessed.
    "https://www.palantir.com/offerings/",
    "https://www.palantir.com/offerings/health/",
    "https://www.palantir.com/offerings/federal-health/",
    "https://www.palantir.com/offerings/palantir-for-hospitals/",
    "https://www.palantir.com/offerings/financial-services/",
    "https://www.palantir.com/offerings/anti-money-laundering/",
    "https://www.palantir.com/offerings/insurance/",
    "https://www.palantir.com/offerings/manufacturing/",
    "https://www.palantir.com/offerings/semiconductors/",
    "https://www.palantir.com/offerings/automotive-mobility/",
    "https://www.palantir.com/offerings/energy/",
    "https://www.palantir.com/offerings/utilities/",
    "https://www.palantir.com/offerings/supply-chain/",
    "https://www.palantir.com/offerings/supply-chain-risk-management/",
    "https://www.palantir.com/offerings/retail/",
    "https://www.palantir.com/offerings/consumer-goods/",
    "https://www.palantir.com/offerings/food-and-beverage/",
    "https://www.palantir.com/offerings/telecommunications/",
    "https://www.palantir.com/offerings/life-sciences/",
    "https://www.palantir.com/offerings/gxp-solutions/",
    "https://www.palantir.com/offerings/defense/",
    "https://www.palantir.com/offerings/intelligence/",
    "https://www.palantir.com/offerings/government-web-services/",
    "https://www.palantir.com/offerings/data-protection/",
    "https://www.palantir.com/offerings/data-mesh/",
    "https://www.palantir.com/offerings/procurement/",
    "https://www.palantir.com/offerings/edge-ai/",
    "https://www.palantir.com/offerings/iot/",
    "https://www.palantir.com/offerings/hyperauto/",
    "https://www.palantir.com/offerings/mixed-reality/",
    "https://www.palantir.com/offerings/construction/",
    "https://www.palantir.com/offerings/readiness/",
]

# Pages known (or suspected) to require login / an account — do not add to
# SEED_URLS. Extract these by hand into data/raw/manual/ if you have access.
GATED_NOTES = [
    "Most of /docs/foundry/ beyond top-level overview pages requires a Foundry account.",
    "AIP Studio / Ontology SDK reference docs typically require login.",
]
