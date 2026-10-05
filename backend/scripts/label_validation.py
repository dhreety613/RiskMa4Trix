"""Samples ~50 already-classified risk paragraphs into a CSV for the
owner to hand-label a `true_category` column. eval_classifier.py then
compares the classifier's prediction against those hand labels - no
accuracy number gets written anywhere until this has actually happened
(CLAUDE.md: "no fabricated metrics... unmeasured -> pending").

Run from backend/:
    python -m scripts.label_validation --out validation_sample.csv
"""

import argparse
import csv
import random

from app.db import SessionLocal
from app.models import Risk, Taxonomy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="validation_sample.csv")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    db = SessionLocal()
    risks = db.query(Risk).filter(Risk.status == "active").all()
    taxonomy = {t.id: t.slug for t in db.query(Taxonomy).all()}
    db.close()

    if not risks:
        raise SystemExit("No risks in the DB yet - run seed_companies.py first.")

    random.seed(args.seed)
    sample = random.sample(risks, min(args.n, len(risks)))

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["risk_id", "company_id", "title", "text", "predicted_category", "true_category"]
        )
        for risk in sample:
            predicted = taxonomy.get(risk.category_id, "") if risk.category_id else "unclassified"
            writer.writerow([risk.id, risk.company_id, risk.title, risk.text, predicted, ""])

    print(f"Wrote {len(sample)} rows to {args.out}")
    print("Fill in the 'true_category' column (use the same taxonomy slugs"
          " from config_data/taxonomy.yaml, or 'unclassified'), then run:")
    print(f"  python -m scripts.eval_classifier --labeled {args.out}")


if __name__ == "__main__":
    main()
