# Ma3Trix — build context

Finance risk platform. For a company: ingest 10-K + financial facts + prices
+ news -> extract risks from the 10-K (retrieval/classification, never free
LLM extraction) -> clean/dedupe -> track drift across filings -> score
probability + impact with math/finance (no LLM scoring) -> 4T risk matrix
(Tolerate/Treat/Transfer/Terminate) -> Monte Carlo + mitigations on Treat
risks only. Also a Data Analyst portfolio piece: SQL-heavy, defensible
methodology, honest about limitations.

Owner style: terse, implementation-first. Minimal explanations. Decide from
this file; only ask when genuinely blocked.

## Stack (fixed - do not substitute)

Backend: FastAPI (3.11+), SQLAlchemy 2.0, Alembic, psycopg3, Pydantic v2.
DB: Postgres 16 + pgvector (HNSW indexes, cosine ops).
Frontend: React + TS + Vite, Tailwind v4, Recharts, TanStack Query, React
Router.
Embeddings: fastembed, `BAAI/bge-small-en-v1.5` (384-dim, ONNX).
Math: numpy, scipy, pandas.
Data sources: SEC EDGAR API (not sec_edgar_downloader - direct submissions
JSON + XBRL companyfacts), yfinance, Google News RSS.
LLM: optional, OFF by default (`LLM_ENABLED=false`). Only ever for (a)
one-line risk titles, (b) mitigation wording polish. **Never** for
classification or scoring.
Docker everywhere; docker-compose for local; render.yaml for deploy.

## Hard rules

- No LLM in scoring or classification decisions. Ever.
- No fabricated metrics anywhere (README, docs, UI). Unmeasured -> "pending".
- Every assumption (priors, driver maps, thresholds) lives in
  `backend/app/config_data/*.yaml` with a `source`/`rationale` field.
- Mandatory honest-limitations section: disclosure frequency != event
  probability; category->driver map is assumption-driven; news is a noisy
  evidence signal; single-risk MC ignores correlation (portfolio/copula is
  future work).
- Pipeline must be idempotent (re-ingest doesn't duplicate rows).
- Respect SEC rate limits (10 req/s), proper User-Agent (`SEC_USER_AGENT`
  env var, "<app name> <email>"). Cache aggressively.

## Where things live

- `backend/app/models.py` - SQLAlchemy models, one table per pipeline step.
- `backend/alembic/versions/` - migrations. Generate with `alembic
  revision --autogenerate`, but **always hand-check the diff** - the
  pgvector import and the `CREATE EXTENSION vector` / HNSW index statements
  do NOT get added automatically and must be inserted manually every time
  a vector column changes (see migration 001 for the pattern).
- `backend/app/ingest/` - edgar.py, financials.py, prices.py, news.py.
- `backend/app/extract/` - splitter.py, embedder.py, classifier.py,
  titles.py.
- `backend/app/clean/` - dedupe.py, boilerplate.py.
- `backend/app/drift/` - matcher.py, tone.py.
- `backend/app/scoring/` - probability.py, impact.py, zones.py.
- `backend/app/montecarlo/` - simulate.py, mitigation.py.
- `backend/app/config_data/` - taxonomy.yaml, category_priors.yaml,
  category_drivers.yaml, mitigations.yaml - every assumption, with sources.
- `frontend/src/pages/` - Home, Company, Matrix, Drift, Methodology.
- `docs/METHODOLOGY.md` - every formula + assumption + limitation.
- `docs/VALIDATION.md` - classifier eval, measured numbers only.

## Reference repo (read-only, do not copy its architecture)

`github.com/dhreety613/rishmAtrIx` - the owner's earlier attempt. It is
**entirely LLM-extraction based** (Gemini free-text over news headlines and
raw 10-K chunks) - exactly what this rebuild is replacing. Worth reusing
only:
- the Item 1A regex boundary idea (`risk-extraction/utils.py
  extract_risk_section`) as a seed for `splitter.py`, not as-is.
- BeautifulSoup HTML->text cleaning approach.
- Google News RSS URL pattern (`news.google.com/rss/search?q=...` via
  `feedparser`) for `ingest/news.py`.
Everything else there (Gemini risk extraction, the `likelihood * impact`
3T scoring in `risk_matrix_generator.py`) is what we are explicitly NOT
doing again.

## Local dev notes

- A native Postgres may already be running on the host's 5432 - the
  compose file maps the pgvector container to host port **5433** instead
  (internal Docker network traffic between `api` and `postgres` still uses
  `postgres:5432` and is unaffected).
- `backend/.venv` exists for running alembic/pytest/ruff directly on the
  host without Docker. Note: the host Python is 3.10, but `pyproject.toml`
  pins `requires-python = ">=3.11"` (matches the Docker image) - so the
  venv has dependencies installed directly (not `pip install -e .`) and
  needs `PYTHONPATH=.` set when running scripts from `backend/`.
- Full stack: `docker compose up` (reads `.env` - copy from `.env.example`
  first).

## Phase status

- [x] Phase 1 - Foundation: repo, docker-compose (api + postgres/pgvector +
  frontend), Alembic migration 001 (full schema), health endpoint, CI,
  frontend scaffold with a live health check. Verified: migration applies
  cleanly, pgvector + HNSW indexes exist, backend tests/ruff pass, frontend
  tsc/build pass.
- [x] Phase 2 - Ingestion (EDGAR, financials, prices, news,
  seed_companies.py). Verified end-to-end against real data (AAPL, MSFT)
  both via the local venv and the actual running Docker container:
  CIK lookup, 5yr 10-K listing, Item 1A/7/7A extraction, XBRL financial
  facts, yfinance price stats, Google News RSS, idempotent re-ingest (no
  duplicate rows). Two real bugs found and fixed while testing against
  live AAPL filings - worth knowing about if this code is touched again:
  1. `edgar.extract_sections`: naively taking the textually-last
     occurrence of "Item 1A"/"Item 7" picks up prose cross-references
     ("as described in Item 1A of this Form 10-K...") instead of the
     real section header. The exact fix evolved further in Phase 3 (see
     below) - this first pass (require canonical title immediately
     after + pick the longest span) was NOT the final version.
  2. `yfinance`'s `FastInfo.get("market_cap")` silently returns `None`
     (wrong key - it's camelCase `marketCap`) instead of raising, so the
     bug doesn't surface as an error, just silently-missing data.
  Also: SEC's own ticker->CIK map (`company_tickers.json`) can point a
  ticker at a *newly restructured successor entity* whose XBRL history
  only goes back to its creation date (e.g. XOM -> "ExxonMobil Holdings
  Corp", CIK 2115436, with no FY2023/2024 10-K facts at all under that
  CIK). That's not a bug - financial facts correctly come back `None`
  for those years, which is the honest/pending behavior the hard rules
  ask for, not something to "fix" by chasing predecessor CIKs.
- [x] Phase 3 - Risk extraction: splitter.py, taxonomy.yaml (50
  categories), embedder.py (fastembed), classifier.py (cosine kNN vs
  per-example vectors, NOT per-category centroids - see below), titles.py
  (template default, optional LLM polish), news classification + linking,
  label_validation.py/eval_classifier.py (genuinely pending - see
  docs/VALIDATION.md, no self-labeled numbers written).

  `edgar.extract_sections`'s header-boundary logic (from Phase 2) turned
  out to need THREE rounds of fixes before it held up across 5 real,
  structurally different filers (AAPL, NVDA, MSFT, JPM, JNJ) - each
  fix broke on the next filer's own HTML quirk, so if this is touched
  again, re-run the same check across multiple diverse tickers, not
  just the one that prompted the change:
  1. **AAPL**: a cross-reference anywhere in the document that restates
     the title right after the item number ("as described in Item 1A of
     this Form 10-K...") gets mistaken for the real header by a naive
     "last occurrence" search. Fix: require the canonical title text to
     immediately follow the item number.
  2. **NVIDIA**: that fix alone isn't enough - an EARLY cross-reference
     that also happens to restate the title (with a comma, or with NO
     punctuation at all before continuing into lowercase prose) shares
     the same later end-boundary as the real header, so it produces a
     LONGER span and wins under "longest span wins". Fix: also require
     that whatever immediately follows the matched title is a line
     break (or the bold-sentinel, or a single trailing period/colon then
     a line break) - a real header is always alone on its own line;
     prose never is.
  3. **Microsoft**: its inline-XBRL renderer sometimes splits a single
     word's bolding across TWO adjacent spans, including mid-word
     ("RISK" rendered as "RIS" + a fresh bold span + "K", which
     flattens to "RIS\n\x01\n\x01\nK FACTORS") - breaking the literal
     "risk factors" match entirely. Fix: match titles against a
     SQUASHED (alphanumeric-only, whitespace/punctuation/bold-sentinels
     stripped) version of the lookahead text, with a position map back
     to the original text so the line-break boundary check (point 2)
     still works on the real, unsquashed text.
  4. **JPMorgan**: its real header is "Item 1A. Risk Factors.\nThe
     following..." - a trailing PERIOD between the title and the line
     break, which the line-break check (point 2) didn't tolerate. Fix:
     skip at most one trailing period/colon (plus stray non-breaking
     spaces) before checking for the line break.
  5. Item 8's canonical title varies by filer ("Financial Statements"
     vs "...and Supplementary Data") - matching only the short form left
     real title text before the real line break for filers using the
     long form, which looked exactly like a cross-reference and got
     rejected, silently breaking Item 7A's end-of-section boundary (item
     7A has no OTHER end marker, so it fell back to end-of-document).
     Fix: try multiple known title variants per item, longest first.

  Known remaining limitation: `item7_text`/`item7a_text` extraction is
  noticeably less robust than `item1a_text` across filers (e.g. JPM's
  item7 came back only 395 chars; JNJ's came back empty) - likely more
  filer-specific title/formatting variance in that part of the document
  that the same fixes above haven't been checked against as thoroughly.
  Not fixed further for now because `item1a_text` is the only one
  consumed by the actual extraction pipeline (splitter -> classifier);
  item7/item7a are stored on `Filing` only for human context.

  Classifier-specific findings:
  - Centroid-of-examples-per-category (averaging 5-8 example embeddings
    into one vector per category) let one generic-sounding category
    ("credit risk") win on paragraphs that had nothing to do with it -
    switched to max-similarity-against-any-single-example instead.
  - The embedding model's baseline/noise similarity floor is higher than
    a naive guess: pure gibberish still scored ~0.58 against the
    taxonomy. `UNCLASSIFIED_THRESHOLD` is 0.6, set from that observation,
    not from a labeled validation set (still pending).
  - News-risk linking needs BOTH a category match AND embedding
    similarity above threshold (CLAUDE.md's own spec says this
    explicitly) - similarity alone, without the category filter, linked
    one ordinary day's news to the majority of all risk x news pairs
    across 65 risks and 30 headlines, which is useless as "evidence for
    this specific risk."

  Real concurrency bug found and fixed: `ensure_taxonomy_seeded`'s
  original check-then-insert pattern raised `UniqueViolation` when two
  `/companies/{ticker}/ingest` requests' BackgroundTasks happened to run
  close together (confirmed with AAPL + JPM queued back-to-back) - both
  background tasks query "does this slug exist?", both see no, both try
  to INSERT. Fixed with an atomic `INSERT ... ON CONFLICT DO UPDATE`
  instead. `ingest/pipeline.py`'s `upsert_company` has the exact same
  check-then-insert shape and would have the same race for two
  concurrent ingests of the SAME ticker - not hit in testing, not fixed
  yet, worth the same treatment if it ever actually happens.
- [x] Phase 4 - Cleaning: dedupe.py (pgvector cosine > 0.90 within a
  filing, union-find for transitive merges, keeps the longest text,
  soft-deletes the rest as status="merged" rather than hard-deleting -
  existing risk_scores/news_risk_links/mc_runs FKs stay valid).
  boilerplate.py (generic_score = fraction of OTHER companies in the
  whole DB with a near-duplicate risk, >=0.85 cosine; is_generic at
  >=0.5). CI now runs a real pgvector/pgvector:pg16 service + `alembic
  upgrade head` before pytest, since dedupe/boilerplate (and every DB-
  backed phase from here on - drift, scoring) need a real Postgres, not
  SQLite (pgvector columns have no SQLite equivalent). Added
  `tests/conftest.py`'s `db` fixture (rolls back after each test -
  tests must use `db.flush()`, never `db.commit()`, or rollback can't
  undo them).

  Verified against real re-ingested AAPL + MSFT data (216 active risks
  after 1 genuine near-duplicate merge): with only 2 companies in the
  DB, generic_score is necessarily binary (0.0 or 1.0 - there's only
  ONE "other company" to possibly match), so the 49/216 risks flagged
  generic at exactly 1.0 is expected, not a bug; it'll show real
  fractional values once more companies are seeded.

  Known limitation, not fixed (documented per the honesty-about-
  limitations rule rather than chased further): the spec also asks to
  "drop non-risk paragraphs (intro text, forward-looking statements)" -
  there's no separate filter for this. In practice the generic
  boilerplate intro paragraph every filer includes (e.g. AAPL's "The
  following summarizes factors that could have a material adverse
  effect...") becomes its own Risk row and only gets flagged
  `is_generic` once enough OTHER companies are in the DB to recognize
  it as shared language - with very few companies seeded, it shows up
  in the matrix like a real risk. A dedicated phrase-pattern filter for
  this would hit the same filer-specific whack-a-mole problem Phase 3's
  section-boundary detection did; relying on boilerplate detection to
  catch it as the DB grows was the pragmatic call given time already
  spent on Phase 3.
- [x] Phase 5 - Risk drift: matcher.py (Hungarian/`linear_sum_assignment`
  on the cosine-similarity matrix between two consecutive filings' active
  risks - NOT greedy nearest-neighbor, so one risk can't steal the best
  match meant for a different risk; >=0.80 persisting, 0.65-0.80
  reworded, below that or unmatched -> removed/new instead of forcing a
  low-confidence pairing). tone.py (Loughran-McDonald neg/uncertainty
  word ratios per filing per category, mean risk position, risk count -
  see config_data/lm_dictionary/README.md: curated ~140/~100-word subset,
  not the full published LM Master Dictionary, documented as a
  limitation rather than silently presented as the real academic metric).
  Both wired into extract_for_company; idempotent (drift clears existing
  events for a from/to filing pair first, tone clears existing stats for
  a filing first, before re-inserting).

  Verified against real re-ingested AAPL data (5 filings, FY2021-2025):
  4 consecutive year-pairs, overwhelmingly "persisting" (18-20 of ~20-25
  risks each year) with small new/removed/reworded counts - exactly the
  expected pattern for a stable large filer. Tone ratios landed in a
  plausible 1-4% range for formal corporate risk language. Drift
  dashboard itself (frontend heatmap/list/trend line) is Phase 7's job,
  not built yet - this phase is the API-less backend computation only.
- [x] Phase 6 - Scoring: probability.py (Beta-Bernoulli - prior per
  category from category_priors.yaml, evidence = distinct months in the
  trailing 12 with >=1 linked news item, + a drift pseudo-count when the
  risk's most recent appearance was flagged "new"). impact.py (exposure
  x shock -> Impact$ -> %EBITDA, fallback %market-cap; log-scaled 0-1
  impact_norm + 1-5 band). zones.py (4T from (P, impact_norm), thresholds
  configurable - P>=0.20, impact_norm>=0.50 by default, judgment calls
  not fit to data). Every category_priors.yaml/category_drivers.yaml
  entry has a source/rationale field (mostly "assumption" - a few cite
  a real reference point like NBER recession frequency).

  Key simplification, documented rather than hidden: category_drivers.yaml
  only has two driver types (`interest_rate`, using actual total_debt;
  `revenue_share` for everything else, using an assumed revenue-share %
  x the company's own historical dd95_1y as a generic severity proxy).
  The spec's richer per-category drivers (foreign revenue share for FX,
  top-customer share for concentration, floating-rate debt specifically)
  aren't usable because Phase 2 never ingested those specific XBRL
  facts - every risk score's `fallbacks` field records this each time it
  fires, so the UI's "assumption-driven" badge is honest rather than
  silent.

  Verified against real re-ingested AAPL data (FY2025 filing, 20 active
  risks, all 20 scored): expected-loss figures landed at a plausible
  scale (hundreds of millions to ~$1.2B, proportioned to Apple's
  ~$135B EBITDA); zones split tolerate/transfer/treat with none hitting
  terminate - consistent with no current news evidence or "new"-drift
  risks pushing any single risk's probability high enough to combine
  with high impact simultaneously.
- [ ] Phase 7 - Matrix + risk cards (frontend + API)
- [ ] Phase 8 - Monte Carlo + mitigations
- [ ] Phase 9 - Deploy (Render) + docs (README, METHODOLOGY, VALIDATION)
