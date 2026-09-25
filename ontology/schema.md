# Capability Ontology Schema

`capability_ontology.yaml` has three top-level sections.

## `primitives`

The generalized, industry-agnostic building blocks. This is the actual
deliverable — everything else in the file is evidence/justification for these.
Each entry:

- `id` — stable snake_case key, safe to reference from other systems (e.g. Locus
  entity IDs).
- `name` — human-readable name of the generic pattern (not Palantir's product name).
- `palantir_terms` — the vendor-specific names this was abstracted from, kept for
  traceability back to source material.
- `generic_pattern` — 1-3 sentences describing the pattern with zero vendor
  vocabulary. This is what should transfer to Panderose/Clerid.
- `depends_on` — ids of other primitives this one assumes exist (most build on
  `semantic_data_layer`).
- `panderose_relevance` — a short, honest note on whether/how this maps onto
  Clerid, Locus, or the context-server work. Left blank (`null`) where there's
  no clear mapping yet rather than forcing one.
- `evidence` — which fetched source pages this was drawn from (matches
  `data/raw/manifest.json` slugs).

## `industry_applications`

Evidence that the *same* primitive set recurs across verticals rather than each
industry getting bespoke architecture. Each entry: `industry`, `primitives_used`
(ids from above), `example` (one concrete instantiation pulled from source text,
with attribution).

## `sources`

Flat list of `{url, slug, fetched_at}` for everything actually used, so every
claim in this file can be traced back to a specific fetched page. If a claim
here can't be traced to an entry in this list or to `data/raw/manual/`, it
shouldn't be in the file — flag it for removal rather than leaving it unsourced.
