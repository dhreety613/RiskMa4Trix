# Ma3Trix

**A finance risk platform that turns 10-K risk factors into a live, scored 4T risk matrix - built with classification and statistics, not an LLM guessing numbers.**

Live demo: **https://ma3trix-frontend.onrender.com** (API: https://ma3trix-api.onrender.com) - deployed on Render's free tier, so the backend spins down when idle (first request after a while takes ~30-60s to wake it up) and the free Postgres instance expires 30 days after creation (2026-11-04); see [Scaling](#scaling--further-improvements) for the fix on both. `GET /companies/AAPL/filings` on the live API already shows 5 real ingested 10-Ks; full extraction+scoring for a demo company is still finishing on this tier as of this writing (see the free-tier background-task limitation below) - the pipeline is verified complete end-to-end locally via `docker compose up` (see `CLAUDE.md`'s phase log for every step confirmed against real data).

> **Screenshots**: this build was done entirely from a CLI coding session with no browser-automation tooling available (confirmed empirically - see `CLAUDE.md`), so there are no real screenshots in this README. The live demo link above is the actual verification; screenshots can be added from it directly.

## Table of contents

- [Problem statement](#problem-statement)
- [Solution](#solution)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [What each module does](#what-each-module-does)
- [Choices made, and the alternative considered](#choices-made-and-the-alternative-considered)
- [Bugs found and fixed during development](#bugs-found-and-fixed-during-development)
- [Limitations](#limitations)
- [Scaling / further improvements](#scaling--further-improvements)
- [Running it yourself](#running-it-yourself)
- [License](#license)

## Problem statement

A public company's 10-K "Risk Factors" section (Item 1A) is the single
richest disclosure of what could actually hurt the business - but it's
30-80 pages of dense legal prose, repeated with small wording changes
every year, with no structure, no scoring, and no way to compare across
companies or track how a specific risk's language has drifted over time.
Existing "risk matrix" tools either (a) ignore 10-Ks entirely and rely on
analyst judgment, or (b) feed the whole filing to an LLM and ask it to
invent a probability and impact number - which is fast, but is not
something you can defend in an interview, an audit, or a board meeting:
there's no methodology behind the number, and it can't be reproduced.

## Solution

Ma3Trix treats this as a data pipeline, not a prompt:

- **Ingests** 10-K filings (last 5 years), XBRL financial facts, price
  history, and news - directly from SEC EDGAR and yfinance, not a
  third-party scraper.
- **Extracts** individual risk factors from Item 1A using the real 10-K
  convention (each risk's own bolded lead sentence), then **classifies**
  each one against a 54-category taxonomy by embedding similarity - a
  retrieval method, not free-text LLM extraction.
- **Cleans** the result: merges near-duplicate risks within a filing,
  flags boilerplate language shared across most companies in the
  database.
- **Tracks drift**: matches each risk to its counterpart in the prior
  year's filing (optimal assignment, not nearest-neighbor guessing) and
  labels it new / removed / persisting / reworded, plus a
  Loughran-McDonald tone signal per category per year.
- **Scores** every risk with a Beta-Bernoulli probability model (prior +
  news evidence + drift signal) and a finance-based impact model
  (exposure x shock -> % of EBITDA) - **zero LLM involvement in any
  score**, ever.
- **Plots** the result on a 4T matrix (Tolerate / Treat / Transfer /
  Terminate), with a risk card per point showing exactly which
  assumptions fed the score.
- **Simulates**: for any Treat-zone risk, a real frequency-severity
  Monte Carlo (Poisson event count x lognormal severity), with
  mitigation playbooks that show the before/after VaR/CVaR.
- **Is honest about what it doesn't know**: every assumption lives in a
  YAML file with a `source`/`rationale` field; every score records which
  fallbacks fired; the classifier's accuracy is explicitly "pending"
  until real hand-labeled data exists (see `docs/VALIDATION.md`) rather
  than a fabricated number.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.11), SQLAlchemy 2.0, Alembic, psycopg3, Pydantic v2 |
| Database | Postgres 16 + pgvector (HNSW, cosine ops) |
| Frontend | React 19 + TypeScript + Vite, Tailwind v4, Recharts, TanStack Query, React Router |
| Embeddings | fastembed, `BAAI/bge-small-en-v1.5` (384-dim, ONNX, CPU-friendly) |
| Math | numpy, scipy, pandas |
| Data sources | SEC EDGAR (submissions + XBRL companyfacts APIs), yfinance, Google News RSS |
| LLM | optional, **off by default** - only ever for a risk's one-line title or mitigation wording, never a score or category |
| Infra | Docker Compose (local), Render (deploy) - web service + static site + managed Postgres |
| CI | GitHub Actions - ruff + pytest (against a real pgvector Postgres service) for the backend, oxlint + tsc + vite build for the frontend |

## Project structure

```
ma3trix/
├── render.yaml                  # Render Blueprint (infra as code)
├── docker-compose.yml           # local dev: postgres + api + frontend
├── CLAUDE.md                    # full build log - every bug found, every decision made
├── .github/workflows/ci.yml
├── backend/
│   ├── Dockerfile
│   ├── alembic/                 # migrations (001: full schema, 002: a unique constraint)
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router mount
│   │   ├── config.py            # env-driven settings (pydantic-settings)
│   │   ├── db.py                # SQLAlchemy engine/session
│   │   ├── models.py            # every table - one per pipeline step
│   │   ├── schemas.py           # Pydantic API response shapes
│   │   ├── api/                 # companies, matrix, drift, risks, montecarlo routers
│   │   ├── ingest/               # edgar.py, financials.py, prices.py, news.py, pipeline.py
│   │   ├── extract/              # splitter.py, embedder.py, classifier.py, titles.py, pipeline.py
│   │   ├── clean/                 # dedupe.py, boilerplate.py
│   │   ├── drift/                 # matcher.py, tone.py, pipeline.py
│   │   ├── scoring/               # probability.py, impact.py, zones.py, pipeline.py
│   │   ├── montecarlo/            # simulate.py, mitigation.py
│   │   └── config_data/           # taxonomy.yaml, category_priors.yaml,
│   │                               # category_drivers.yaml, mitigations.yaml, lm_dictionary/
│   ├── scripts/                   # seed_companies.py, label_validation.py, eval_classifier.py
│   └── tests/                     # one file per module above, + conftest.py's db fixture
├── frontend/
│   └── src/
│       ├── pages/                # Home.tsx, Company.tsx
│       ├── components/           # MatrixChart.tsx, RiskCard.tsx
│       ├── api.ts, types.ts, zoneColors.ts
└── docs/
    ├── METHODOLOGY.md            # every formula, every assumption, every limitation
    └── VALIDATION.md             # classifier accuracy - genuinely pending real labels
```

## What each module does

### `backend/app/models.py` - the schema is the pipeline

Every table maps 1:1 to a pipeline stage - `companies` -> `filings` ->
`risks` -> `risk_scores` -> `mc_runs`. The two embedding columns use
pgvector directly:

```python
class RiskEmbedding(Base):
    __tablename__ = "risk_embeddings"
    __table_args__ = (
        Index(
            "ix_risk_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id"), primary_key=True)
    embedding: Mapped[Any] = mapped_column(Vector(EMBED_DIM))
```

### `backend/app/ingest/edgar.py` - filing fetch + section boundaries

Talks to SEC's own `company_tickers.json` + `submissions`/`companyfacts`
JSON APIs directly (not the `sec_edgar_downloader` package, which only
hands back whole-submission text blobs). The hard part turned out to be
finding where Item 1A actually *starts and ends* - see
[Bugs found and fixed](#bugs-found-and-fixed-during-development).

### `backend/app/extract/splitter.py` - one risk, one paragraph

```python
def _is_risk_heading(span_text: str) -> bool:
    cleaned = span_text.replace("\xa0", " ").strip()
    return len(cleaned) >= MIN_HEADING_LEN and cleaned.endswith(".")
```

Each risk factor in a real 10-K starts with its own bolded lead
sentence; a bolded *group* header ("Business Risks") doesn't end in a
period. That one textual cue - confirmed against five real, structurally
different filers - is the entire splitting rule. Filers that don't bold
each risk fall back to blank-line paragraph splitting.

### `backend/app/extract/classifier.py` - retrieval, not generation

```python
def classify_text(text: str) -> ClassificationResult:
    example_slugs, example_vectors = _example_vectors()
    vector = _normalize(embed_texts([text]))[0]
    similarities = example_vectors @ vector
    best_per_category = {...}  # max similarity per category, not a centroid
    ...
    if top1_sim < UNCLASSIFIED_THRESHOLD:
        return ClassificationResult(category_slug=None, ...)
```

A risk paragraph's embedding is compared against every taxonomy
category's *individual* example phrases (max similarity wins), not a
single averaged centroid per category - centroid-averaging let one
generic-sounding category win on paragraphs that had nothing to do with
it (see bugs below).

### `backend/app/drift/matcher.py` - optimal assignment, not nearest-neighbor

```python
row_idx, col_idx = linear_sum_assignment(-similarity)
```

Matching last year's risks to this year's with simple nearest-neighbor
lets one risk "steal" the best match meant for a different risk. The
Hungarian algorithm finds the single assignment that maximizes total
similarity across *all* pairs at once.

### `backend/app/scoring/probability.py` + `impact.py` - the math, in full

```python
alpha = p0 * n0 + k + d
beta = (1 - p0) * n0 + (12 - k)
p_mean = alpha / (alpha + beta)
```

`p0`/`n0` are a category's prior (from `category_priors.yaml`); `k` is
how many of the last 12 months had linked news evidence for *this*
risk; `d` is +1 if drift matching flagged this risk "new." No LLM touches
this number.

```python
impact_usd = exposure * shock
impact_pct_ebitda = impact_usd / ebitda if ebitda > 0 else impact_usd / mcap
```

### `backend/app/montecarlo/simulate.py` - compound Poisson, vectorized

```python
n_events = rng.poisson(lam=params.lam * params.horizon_years, size=n_sims)
severities = rng.lognormal(mean=math.log(params.median_severity), sigma=params.sigma,
                            size=(n_sims, max_events))
losses = (severities * event_mask).sum(axis=1)
```

100,000 simulated years in one vectorized call; same seed reproduces the
same result bit-for-bit (tested).

### `frontend/src/components/MatrixChart.tsx` - the matrix itself

A Recharts scatter plot (P on x, impact on y) with tinted, labeled
quadrant backgrounds and a fixed status-color palette (green/amber/
orange/red) for the four zones - because a 4T zone *is* a severity
escalation, that mapping is a deliberate fit, not decoration.

## Choices made, and the alternative considered

| Decision | Chosen | Alternative considered | Why |
|---|---|---|---|
| Risk extraction | Embedding classification against a curated taxonomy | Ask an LLM to read the filing and list risks with scores | An LLM number has no reproducible methodology - can't defend it in an audit. Classification is deterministic given the same taxonomy and model version. |
| Embedding model | `BAAI/bge-small-en-v1.5` via fastembed (ONNX, CPU) | OpenAI/Cohere embeddings API | No API key, no per-call cost, no network dependency for a step that runs on every risk paragraph of every filing. |
| Category matching | Max similarity across individual examples | A single averaged centroid per category | Centroid-averaging measurably let a generic category win on unrelated paragraphs (see bugs) - confirmed, not theoretical. |
| Risk drift matching | Hungarian algorithm (`scipy.linear_sum_assignment`) | Greedy nearest-neighbor matching | Greedy lets one risk claim a match meant for another; Hungarian finds the single assignment maximizing total similarity. |
| Probability model | Beta-Bernoulli (prior + news/drift evidence) | A flat, hand-set probability per category | Bayesian updating lets evidence move the number over time without a human re-touching every risk. |
| Impact driver | Mostly a revenue-share assumption + the company's own historical drawdown | Category-specific drivers (foreign revenue share, top-customer concentration, etc.) | The specific XBRL facts for the richer drivers were never ingested (a real time cut, documented) - the simpler model at least uses *real* ingested numbers (revenue, debt, EBITDA, price history) rather than a second layer of invented structure. |
| Monte Carlo severity tail | `q95 = 3x median` (a stated assumption) | Fit a tail distribution to historical loss data | No historical loss dataset exists for this project; an explicit, documented multiplier is more honest than quietly fitting noise. |
| Deployment | Direct Render API calls (`POST /v1/postgres`, `POST /v1/services`) | Render's dashboard "New Blueprint Instance" flow | Render's REST API has no "create Blueprint from repo" endpoint (only validate/update/list) - direct service creation was the only fully-API-driven path. `render.yaml` still documents the same topology for a dashboard-based Blueprint sync later. |
| Database | Managed Postgres + pgvector | A dedicated vector DB (Pinecone, Qdrant) | One database for relational data AND vectors - no second system to keep in sync, and the risk/news tables are small enough (thousands of rows) that a dedicated vector DB's scale advantages don't apply yet. |

## Bugs found and fixed during development

All found by testing against real SEC filings, not hypothetically -
`CLAUDE.md` has the full detail on each. The headline ones:

1. **Section-boundary detection broke on every new filer tested.** A
   naive "find Item 1A" approach was fooled, in order: by prose
   cross-references that restate the section title (AAPL), by an early
   cross-reference sharing the same end-boundary as the real header and
   therefore "winning" under a naive longest-span heuristic (NVIDIA), by
   a single word's bolding split across two adjacent HTML spans
   mid-word (Microsoft), and by a trailing period between the title and
   the real header's line break (JPMorgan). Took four rounds of fixes
   against four different real filers before it held up.
2. **Classifier centroid-averaging let a generic category dominate.**
   Averaging 5-8 example embeddings into one per-category vector
   smeared out the specific wording that actually anchors a category;
   switched to max-similarity-against-any-single-example.
3. **News-risk linking without a category filter was useless.**
   Similarity alone (no category match required) linked one ordinary
   day's news to the majority of all risk x news pairs across 65 risks
   and 30 headlines.
4. **A real concurrency bug**: two `/companies/{ticker}/ingest` requests
   queued close together raced on taxonomy-table seeding (check-then-
   insert), throwing `UniqueViolation`. Fixed with an atomic
   `INSERT ... ON CONFLICT DO UPDATE`.
5. **`yfinance`'s `FastInfo.get("market_cap")`** silently returns `None`
   (the real key is camelCase `marketCap`) instead of raising - the kind
   of bug that doesn't show up as an error, just silently-missing data.

## Limitations

- **No real classifier accuracy number yet** - `docs/VALIDATION.md` is
  genuinely "pending" real hand-labeled data, not omitted by oversight.
- **Impact scoring is assumption-driven for most risk categories** - the
  richer per-category drivers the methodology describes need financial
  facts (foreign revenue share, customer concentration, floating-rate
  debt) that were never ingested. Every time a fallback fires it's
  recorded on the score (`fallbacks`), so the UI's "assumption-driven"
  badge is honest rather than silent.
- **Monte Carlo is single-risk, not portfolio-level** - no correlation
  structure between simultaneously-elevated risks.
- **News is Google News RSS**, a noisy popularity signal, not a
  systematic feed of material events.
- **The Loughran-McDonald word lists are a curated ~140/~100-word
  subset**, not the full published Master Dictionary (~2,000+ words).
- **`item7_text`/`item7a_text` extraction is less robust than
  `item1a_text`** across filers - not fixed further since those two
  fields are stored for human context only, not consumed by the
  pipeline.
- **No visual browser testing was done on the frontend** - this build
  ran in a CLI session with no browser-automation tooling available.
  Verified via `tsc`, `vite build`, `oxlint`, and the live deployed URL's
  API responses - not an actual look at the rendered page.
- **Confirmed on the live deploy: free-tier Render + in-process
  background extraction don't mix well.** `POST /companies/{ticker}/ingest`
  returns immediately (it just queues a `BackgroundTask`), but the real
  work - fetching 5 filings, then embedding and classifying every risk
  paragraph - keeps running after the HTTP response is already sent.
  Filings reliably ingest and persist in full; the process then
  restarts before extraction's first embedding call ever logs
  completion, repeatedly, even with `/health` pinged continuously to
  rule out plain HTTP-idle spin-down. That points at the free tier's
  512MB RAM limit getting hit by the embedding model's footprint rather
  than idle timeout specifically - either way, a `BackgroundTask` dies
  with the process, silently, mid-extraction. The fix is exactly the
  task-queue (and/or bigger instance) change already listed under
  [Scaling](#scaling--further-improvements) - this confirms it's not a
  hypothetical need.

## Scaling / further improvements

- **Database**: the free Postgres instance expires 30 days after
  creation. For anything long-lived, upgrade to a paid Starter instance
  (one dashboard click, or re-run the deploy with `plan: starter` in
  `render.yaml`) - no code or migration changes needed.
- **Move ingestion off in-process `BackgroundTasks` onto a real queue**
  (Celery/RQ, or Render's own Background Workers/Cron Jobs). Confirmed
  on the live free-tier deploy (see Limitations above): a `BackgroundTask`
  can get cut off mid-extraction when Render spins the instance down for
  HTTP inactivity, even though the task itself is still running. A
  durable queue survives that; it would also let
  `python -m scripts.seed_companies`'s ~25-ticker default list (scale up
  by passing more tickers) run companies in parallel instead of one at
  a time. The simplest fix needing zero architecture change: a paid
  (non-free) web service instance doesn't spin down, so this specific
  failure mode goes away on its own - the queue is still the right fix
  for parallelism either way.
- **Real per-category impact drivers**: ingest foreign revenue share,
  top-customer concentration, and floating-vs-fixed debt split from
  XBRL (the tags exist; Phase 2 just didn't reach for them) to retire
  the revenue-share fallback for FX/concentration/rate categories
  specifically.
- **Portfolio Monte Carlo**: simulate all of a company's Treat-zone
  risks together with a copula-based dependence structure instead of
  one risk at a time, for a real aggregate VaR/CVaR.
- **Classifier validation loop**: run `scripts/label_validation.py` +
  `eval_classifier.py` against real hand labels, then use the resulting
  confusion matrix to either expand thin taxonomy categories or merge
  ones that are consistently confused.
- **Drift dashboard UI**: the `/companies/{ticker}/drift` API already
  returns everything needed for a year x category heatmap, a new/
  removed/reworded list, and a tone trend line - no backend work left,
  just the frontend page.
- **Full Loughran-McDonald dictionary**: swap in the real ~2,000-word
  Master Dictionary from Notre Dame's SRAF
  (https://sraf.nd.edu/loughranmcdonald-master-dictionary/) for
  `config_data/lm_dictionary/*.txt`.

## Running it yourself

```bash
git clone https://github.com/dhreety613/RiskMa4Trix.git
cd RiskMa4Trix
cp .env.example .env   # set SEC_USER_AGENT to "<your app name> <your email>"
docker compose up
```

- API: http://localhost:8000/health
- Frontend: http://localhost:5173
- Seed some real companies: `docker compose exec api python -m scripts.seed_companies`
- Or ingest one ticker on demand from the frontend's home page (it has a
  ticker search box that triggers `/companies/{ticker}/ingest`)

## License

MIT - see [LICENSE](LICENSE).
