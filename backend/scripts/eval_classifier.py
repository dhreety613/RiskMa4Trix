"""Computes real accuracy/macro-F1/confusion-matrix numbers from a
label_validation.py CSV the owner has filled in by hand, and writes them
to docs/VALIDATION.md. Deliberately not using sklearn for this - it's a
handful of counts, not worth a new dependency.

Run from backend/:
    python -m scripts.eval_classifier --labeled validation_sample.csv
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

VALIDATION_MD = Path(__file__).resolve().parents[2] / "docs" / "VALIDATION.md"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labeled", required=True)
    args = parser.parse_args()

    rows = []
    with open(args.labeled, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["true_category"].strip():
                rows.append(row)

    if not rows:
        raise SystemExit(
            "No rows have 'true_category' filled in - label_validation.py's output "
            "needs hand labels before this can compute anything real."
        )

    correct = sum(1 for r in rows if r["predicted_category"] == r["true_category"])
    accuracy = correct / len(rows)

    classes = sorted({r["true_category"] for r in rows} | {r["predicted_category"] for r in rows})
    tp: Counter = Counter()
    fp: Counter = Counter()
    fn: Counter = Counter()
    confusion: dict[str, Counter] = defaultdict(Counter)

    for r in rows:
        pred, true = r["predicted_category"], r["true_category"]
        confusion[true][pred] += 1
        if pred == true:
            tp[true] += 1
        else:
            fp[pred] += 1
            fn[true] += 1

    f1_scores = {}
    for cls in classes:
        precision = tp[cls] / (tp[cls] + fp[cls]) if (tp[cls] + fp[cls]) else 0.0
        recall = tp[cls] / (tp[cls] + fn[cls]) if (tp[cls] + fn[cls]) else 0.0
        f1_scores[cls] = (
            2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        )
    macro_f1 = sum(f1_scores.values()) / len(f1_scores) if f1_scores else 0.0

    lines = [
        "# Classifier Validation",
        "",
        f"Measured on {len(rows)} hand-labeled risk paragraphs "
        f"(`scripts/label_validation.py` sample, seed 42).",
        "",
        f"- **Accuracy:** {accuracy:.1%} ({correct}/{len(rows)})",
        f"- **Macro-F1:** {macro_f1:.3f}",
        "",
        "## Per-category F1",
        "",
        "| Category | F1 |",
        "|---|---|",
    ]
    for cls, f1 in sorted(f1_scores.items(), key=lambda kv: kv[1]):
        lines.append(f"| {cls} | {f1:.3f} |")

    lines += ["", "## Confusion matrix (true -> predicted counts)", ""]
    for true_cls in classes:
        row_counts = confusion[true_cls]
        if row_counts:
            detail = ", ".join(f"{pred}={n}" for pred, n in row_counts.most_common())
            lines.append(f"- **{true_cls}**: {detail}")

    VALIDATION_MD.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {VALIDATION_MD}")
    print(f"Accuracy: {accuracy:.1%}  Macro-F1: {macro_f1:.3f}")


if __name__ == "__main__":
    main()
