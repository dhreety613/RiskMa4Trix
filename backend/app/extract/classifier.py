"""Cosine-kNN classification of risk paragraphs (and news headlines)
against backend/app/config_data/taxonomy.yaml - NOT free-text LLM
classification (CLAUDE.md hard rule).

Each category's embedding is the centroid of its example phrases'
embeddings. A paragraph's category is whichever centroid it's closest
to by cosine similarity; below UNCLASSIFIED_THRESHOLD it's left
`unclassified` (flagged, not guessed) rather than forced into the
nearest-but-still-distant bucket.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from app.config import CONFIG_DATA_DIR
from app.extract.embedder import embed_texts

TAXONOMY_PATH = CONFIG_DATA_DIR / "taxonomy.yaml"

# Cosine similarity below this -> unclassified rather than forced.
# BAAI/bge-small-en-v1.5 runs a higher generic-similarity floor than a
# naive guess would suggest - pure gibberish still scored ~0.58 against
# the taxonomy's examples during testing (short, generic-sounding
# category phrases apparently sit in a crowded region of the embedding
# space). 0.35 let that gibberish get classified as "internal_controls".
# This is still not tuned against a real labeled set (see VALIDATION.md,
# pending) - just raised past the observed noise floor.
UNCLASSIFIED_THRESHOLD = 0.6


@dataclass
class Category:
    slug: str
    group: str
    name: str
    description: str
    examples: list[str]


@dataclass
class ClassificationResult:
    category_slug: str | None  # None -> unclassified
    confidence: float
    top3: list[tuple[str, float]]


def load_taxonomy(path: Path = TAXONOMY_PATH) -> list[Category]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return [Category(**row) for row in raw]


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


@lru_cache
def _example_vectors() -> tuple[list[str], np.ndarray]:
    """Every example phrase's own embedding, tagged with its category.

    Classifying against each individual example (then taking, per
    category, the single closest example) instead of a per-category
    centroid - averaging 5-8 short examples into one centroid smears
    out the specific wording that actually anchors a category, and in
    practice let a generic-sounding category win on paragraphs that
    don't belong to it (confirmed against real risk paragraphs: a
    5-example centroid for "credit risk" was winning on stock-price and
    boilerplate-intro paragraphs it has nothing to do with).
    """
    categories = load_taxonomy()
    slugs: list[str] = []
    all_examples: list[str] = []
    for cat in categories:
        for example in cat.examples:
            slugs.append(cat.slug)
            all_examples.append(example)
    return slugs, _normalize(embed_texts(all_examples))


def classify_text(text: str) -> ClassificationResult:
    example_slugs, example_vectors = _example_vectors()
    vector = _normalize(embed_texts([text]))[0]

    similarities = example_vectors @ vector

    best_per_category: dict[str, float] = {}
    for slug, sim in zip(example_slugs, similarities, strict=True):
        if slug not in best_per_category or sim > best_per_category[slug]:
            best_per_category[slug] = float(sim)

    ranked = sorted(best_per_category.items(), key=lambda kv: kv[1], reverse=True)
    top3 = ranked[:3]
    top1_slug, top1_sim = top3[0]

    if top1_sim < UNCLASSIFIED_THRESHOLD:
        return ClassificationResult(category_slug=None, confidence=top1_sim, top3=top3)
    return ClassificationResult(category_slug=top1_slug, confidence=top1_sim, top3=top3)
