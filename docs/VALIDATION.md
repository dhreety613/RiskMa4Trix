# Classifier Validation

**Status: pending.** No hand-labeled ground truth exists yet, so there is
no accuracy or F1 number to report - writing one without real labels
would be exactly the kind of fabricated metric CLAUDE.md's hard rules
rule out.

## How to actually measure this

1. Seed some companies if you haven't: `python -m scripts.seed_companies`
2. Sample paragraphs for hand-labeling:
   `python -m scripts.label_validation --out validation_sample.csv`
3. Open the CSV, fill in `true_category` for each row using the slugs in
   `app/config_data/taxonomy.yaml` (or `unclassified`).
4. `python -m scripts.eval_classifier --labeled validation_sample.csv`
   - This overwrites this file with real accuracy, macro-F1, per-category
     F1, and a confusion matrix, computed only from what you labeled.

## Known limitations going in (confirmed during development, not from a
formal eval)

- The taxonomy has coverage gaps: paragraphs about inventory write-downs,
  platform/ecosystem dependency, or stock-price volatility don't have a
  well-matched category and land in a semantically-nearby but not-quite-
  right bucket (e.g. a stock-volatility paragraph landing under "Access to
  Capital"). More categories or better examples would help; this will
  show up as specific per-category F1 weaknesses once real labels exist.
- Few-shot (5-8 examples per category) cosine classification is sensitive
  to example wording. An earlier version of this classifier averaged
  example embeddings into a single per-category centroid, which let one
  generic-sounding category win on paragraphs it had nothing to do with
  (confirmed against real AAPL filings - see CLAUDE.md). Switched to
  max-similarity-against-any-single-example instead, which measurably
  improved results on manual inspection, but that's not the same as a
  real accuracy number.
