# Methodology

Every formula, assumption, and known limitation behind Ma3Trix's risk
matrix, in the order the pipeline actually runs. Where a number is an
assumption rather than a measured quantity, it's labeled as such - this
document follows the same rule as the code and config: no claim without
a stated source.

## 1. Ingestion

- **Filings**: SEC EDGAR's `submissions` API lists a company's 10-Ks for
  the last 5 years; the primary document is fetched directly (not via
  `sec_edgar_downloader`, which only gives whole-submission text blobs).
- **Financial facts**: SEC's XBRL `companyfacts` API, with ordered tag
  fallbacks per metric (filers tag revenue/debt inconsistently). EBITDA
  is a proxy: `OperatingIncomeLoss + DepreciationDepletionAndAmortization`.
  A metric that can't be found for a fiscal year is `null`, never guessed.
- **Prices**: yfinance - annualized volatility (log returns, trailing
  ~1yr), beta vs. the S&P 500, 95th-percentile 1-year drawdown (`dd95_1y`
  - the deepest 5% of observed drawdowns over the window), market cap.
- **News**: Google News RSS, per company name. Evidence, not analysis -
  stored as headlines with a timestamp and source, nothing inferred from
  them at this stage.

## 2. Extraction (classification-first, never free LLM extraction)

- **Splitting**: each risk factor in Item 1A is identified by its own
  bolded lead sentence (a real 10-K convention, confirmed against actual
  filings) - a bold span counts as a risk heading only if it ends in a
  period; bolded *group* headers ("Business Risks") don't, and are
  skipped. Filers that don't bold each risk fall back to splitting on
  blank-line paragraph breaks instead.
- **Classification**: cosine similarity between a risk paragraph's
  embedding (`BAAI/bge-small-en-v1.5`, 384-dim) and each taxonomy
  category's individual example-phrase embeddings (max similarity per
  category, not a per-category centroid - centroid-averaging let one
  generic category win on unrelated paragraphs in testing). Below
  `UNCLASSIFIED_THRESHOLD` (0.6, set from the embedding model's observed
  noise floor - pure gibberish still scored ~0.58 - not from a labeled
  validation set), a risk is left `unclassified` rather than forced into
  a distant match.
- **Titles**: a template (`"<Category>: <first sentence>"`) by default.
  An LLM may *only* polish the wording when `LLM_ENABLED=true` - it never
  decides the category, the score, or the content.
- **News linking**: a news item counts as evidence for a specific risk
  only if it shares that risk's category AND its embedding similarity is
  above `NEWS_RISK_LINK_THRESHOLD` (0.6). Similarity alone, without the
  category match, linked one ordinary day's news to the majority of all
  risk x news pairs in testing - useless as evidence for any one risk.

## 3. Cleaning

- **Dedupe**: risks within the same filing with cosine similarity > 0.90
  are merged (transitively, via union-find) into one, keeping the
  longest text and recording `merged_count`.
- **Boilerplate**: `generic_score` = the fraction of *other* companies
  in the whole database that have at least one risk within 0.85 cosine
  similarity of this one. `is_generic` is true at `generic_score >= 0.5`.
  This is a real cross-company signal, not a phrase list - but it needs
  several companies in the database to mean anything; with very few
  companies, a risk shared by just 2-3 of them can look "generic" even
  if it's a genuinely narrow industry risk.

## 4. Drift

- **Matching**: risks between two consecutive filings of the same
  company are matched by the Hungarian algorithm (`scipy.optimize.
  linear_sum_assignment`) on the full cosine-similarity matrix - an
  optimal global assignment, not greedy nearest-neighbor (which lets one
  risk "steal" the best match meant for another). `similarity >= 0.80`
  -> persisting; `0.65-0.80` -> reworded; below 0.65, or simply
  unmatched, counts as removed (prior filing) / new (current filing)
  instead of forcing a low-confidence pairing.
- **Tone**: Loughran-McDonald negative/uncertainty word ratios per
  filing, per category. The word lists (`config_data/lm_dictionary/`)
  are a curated ~140/~100-word subset written from general knowledge of
  those categories, **not** the full published LM Master Dictionary
  (~2,000+ words) - see that directory's README for where to get the
  real one.

## 5. Scoring (math/finance only - no LLM, ever)

### Probability: Beta-Bernoulli update

```
alpha0 = p0 * n0          beta0 = (1 - p0) * n0
alpha  = alpha0 + k + d    beta = beta0 + (12 - k)
P = alpha / (alpha + beta)       [90% CI from the Beta distribution]
```

- `p0`, `n0` (prior mean, prior strength/pseudo-observations) come from
  `config_data/category_priors.yaml` per category - almost all are
  stated assumptions (a judgment call, not a measured base rate); a
  couple cite a real reference point (NBER recession frequency for
  macro risk, breach-survey frequency for cyber). `n0=10` by default per
  the spec.
- `k` = number of distinct months in the trailing 12 with >=1 news item
  linked to *this specific risk* (not just its category).
- `d` = a drift pseudo-count: +1 if this risk's most recent appearance
  was flagged "new" by drift matching.

### Impact: exposure x shock -> % of EBITDA

```
Impact$   = Exposure x Shock
Impact%   = Impact$ / EBITDA        (or / market cap if EBITDA <= 0)
Expected Loss = P x Impact$
```

- **Driver** (`config_data/category_drivers.yaml`) is one of two types,
  a deliberate simplification: `interest_rate` uses actual total debt
  (an ingested fact) x an assumed rate-shock (200bps default); every
  other category uses `revenue x an assumed revenue-share %` as
  Exposure, and the company's own historical `dd95_1y` as Shock. The
  spec's richer per-category drivers (foreign revenue share for FX,
  top-customer concentration, floating-vs-fixed debt split) aren't used
  because those specific XBRL facts were never ingested - every time
  this fallback fires it's recorded on the score (`fallbacks`), so the
  UI's "assumption-driven" badge reflects real missing data, not a
  silent guess dressed up as a measurement.
- `impact_norm` (0-1, for the matrix's y-axis) is a log-scaled mapping
  of `Impact%` between 0.1% and 100% of EBITDA, banded 1-5.

### Zones (4T)

| | low impact_norm | high impact_norm |
|---|---|---|
| **low P** | Tolerate | Transfer |
| **high P** | Treat | Terminate |

Thresholds (`P_THRESHOLD=0.20`, `IMPACT_THRESHOLD=0.50`) are
configurable judgment calls, not fit to any dataset.

## 6. Monte Carlo (Treat-zone risks only)

Frequency-severity compound process:

```
N ~ Poisson(lambda),  lambda = -ln(1 - P)
Severity ~ Lognormal(median = Impact$, sigma)
Annual loss = sum of N severity draws
```

- `sigma = ln(q95 / median) / 1.645`. There's no independently measured
  tail-loss quantile behind this build, so `q95 = median * 3.0`
  (`DEFAULT_Q95_MULTIPLIER`, a stated assumption) unless the caller
  supplies `sigma` directly via the API.
- All parameters (`p_annual`, `median_severity`, `sigma`, horizon,
  number of simulations, seed) default from the risk's own score but are
  fully overridable - nothing is hardcoded server-side.
- Vectorized with `numpy.random.default_rng(seed)`; same seed -> bit-
  identical result (tested).
- Mitigation (`config_data/mitigations.yaml`, 18 taxonomy-*group*-level
  playbooks, not per the finer-grained 54-category taxonomy - another
  documented scope cut): a user-chosen effectiveness fraction for
  frequency and severity scales `p_annual`/`median_severity` down before
  re-simulating, for a before/after VaR/CVaR comparison.
- Persisted: parameters, seed, summary statistics, a 50-bin histogram,
  and a 100-point exceedance curve - **never the raw simulated samples**.

## Honest limitations (read before trusting a number)

- **Disclosure frequency is not event probability.** A risk being
  disclosed every year doesn't mean it has a 100% annual chance of
  materializing - the probability model treats disclosure + news
  evidence + drift as a Bayesian signal, not a direct measurement.
- **The impact model is assumption-driven for most categories** - see
  §5. The `fallbacks` field on every `RiskScore` row says exactly which
  assumptions fired for that specific risk.
- **News is a noisy evidence signal.** Google News RSS surfaces whatever
  is popular that day, not a systematic feed of material events; a quiet
  news day doesn't mean a risk's probability is actually falling.
- **Single-risk Monte Carlo ignores correlation.** Running simulations
  risk-by-risk (rather than as a portfolio with a dependence structure,
  e.g. a copula) overstates diversification if multiple Treat-zone risks
  would actually spike together (a recession-driven macro + customer-
  credit combination, for instance). True portfolio-level simulation is
  future work.
- **The classifier has no measured accuracy yet.** See
  `docs/VALIDATION.md` - genuinely pending real hand-labeled data, not
  omitted by oversight.
