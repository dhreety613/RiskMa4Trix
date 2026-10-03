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
- [ ] Phase 2 - Ingestion (EDGAR, financials, prices, news, seed_companies.py)
- [ ] Phase 3 - Risk extraction (splitter, taxonomy, classifier, titles,
  news classification, validation)
- [ ] Phase 4 - Cleaning (dedupe, boilerplate)
- [ ] Phase 5 - Risk drift (matcher, tone, dashboard)
- [ ] Phase 6 - Scoring (probability, impact, zones)
- [ ] Phase 7 - Matrix + risk cards (frontend + API)
- [ ] Phase 8 - Monte Carlo + mitigations
- [ ] Phase 9 - Deploy (Render) + docs (README, METHODOLOGY, VALIDATION)
