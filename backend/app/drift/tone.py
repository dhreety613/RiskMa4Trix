"""Per-filing, per-category tone stats: Loughran-McDonald negative and
uncertainty word ratios, plus mean position (earlier in Item 1A = more
prominent) and risk count. See config_data/lm_dictionary/README.md for
the word-list caveat (curated subset, not the full published LM Master
Dictionary).
"""

import re
from collections import defaultdict
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import CONFIG_DATA_DIR
from app.models import Filing, Risk, ToneStat

_WORD_PATTERN = re.compile(r"[a-zA-Z]+(?:-[a-zA-Z]+)?")


@lru_cache
def _load_word_set(filename: str) -> frozenset[str]:
    path = CONFIG_DATA_DIR / "lm_dictionary" / filename
    with open(path, encoding="utf-8") as f:
        return frozenset(line.strip().lower() for line in f if line.strip())


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_PATTERN.finditer(text)]


def compute_tone_for_filing(db: Session, filing: Filing) -> int:
    """Returns the number of tone_stats rows written (one per category
    present in this filing, plus one for uncategorized/unclassified
    risks under category_id=None).
    """
    negative_words = _load_word_set("negative.txt")
    uncertainty_words = _load_word_set("uncertainty.txt")

    risks = db.query(Risk).filter(Risk.filing_id == filing.id, Risk.status == "active").all()

    db.query(ToneStat).filter(ToneStat.filing_id == filing.id).delete()
    if not risks:
        db.flush()
        return 0

    by_category: dict[int | None, list[Risk]] = defaultdict(list)
    for risk in risks:
        by_category[risk.category_id].append(risk)

    written = 0
    for category_id, cat_risks in by_category.items():
        words: list[str] = []
        for risk in cat_risks:
            words.extend(_tokenize(risk.text))
        total_words = len(words) or 1

        neg_count = sum(1 for w in words if w in negative_words)
        unc_count = sum(1 for w in words if w in uncertainty_words)
        mean_position = sum(r.position_idx for r in cat_risks) / len(cat_risks)

        db.add(
            ToneStat(
                filing_id=filing.id,
                category_id=category_id,
                neg_ratio=neg_count / total_words,
                unc_ratio=unc_count / total_words,
                mean_position=mean_position,
                risk_count=len(cat_risks),
            )
        )
        written += 1

    db.flush()
    return written
