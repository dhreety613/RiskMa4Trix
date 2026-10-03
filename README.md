# Ma3Trix

A finance risk platform: 10-K risk extraction (classification, not free LLM
extraction), risk drift tracking across filings, Bayesian probability +
finance-driven impact scoring, a 4T risk matrix (Tolerate / Treat / Transfer
/ Terminate), and Monte Carlo simulation + mitigation planning on Treat-zone
risks.

**Status: work in progress (Phase 1 of 9 complete).** This README will be
replaced with the full write-up (architecture, screenshots, methodology,
validation results, limitations) once the pipeline is far enough along to
report real, measured numbers instead of placeholders - see `CLAUDE.md` for
the phase plan and current status.

## Quickstart (current state)

```bash
cp .env.example .env
docker compose up
```

- API: http://localhost:8000/health
- Frontend: http://localhost:5173
