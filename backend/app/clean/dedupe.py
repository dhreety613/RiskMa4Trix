"""Merges near-duplicate risk paragraphs WITHIN a single filing (pgvector
cosine similarity > DEDUPE_THRESHOLD). Keeps the longest text as the
survivor and soft-deletes the rest (status="merged", not hard-deleted,
so existing risk_scores/news_risk_links/mc_runs FKs stay valid) with
merged_count recording how many were folded in.
"""

from collections import defaultdict

import numpy as np
from sqlalchemy.orm import Session

from app.extract.classifier import _normalize
from app.models import Filing, Risk

DEDUPE_THRESHOLD = 0.90


def _connected_components(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """Union-find: two paragraphs each >0.90 similar to a shared third
    one, but not quite to each other, should still merge as one group -
    similarity alone isn't guaranteed transitive at a hard cutoff.
    """
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in edges:
        union(a, b)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def dedupe_risks_for_filing(db: Session, filing: Filing) -> int:
    """Returns the number of risks merged away (not the number remaining)."""
    risks = (
        db.query(Risk)
        .filter(Risk.filing_id == filing.id, Risk.status == "active")
        .all()
    )
    risks_with_embeddings = [r for r in risks if r.embedding_row]
    if len(risks_with_embeddings) < 2:
        return 0

    vectors = _normalize(
        np.array([r.embedding_row.embedding for r in risks_with_embeddings], dtype=np.float32)
    )
    similarities = vectors @ vectors.T

    n = len(risks_with_embeddings)
    edges = [
        (i, j)
        for i in range(n)
        for j in range(i + 1, n)
        if similarities[i, j] >= DEDUPE_THRESHOLD
    ]
    if not edges:
        return 0

    merged_count = 0
    for group in _connected_components(n, edges):
        if len(group) < 2:
            continue
        group_risks = [risks_with_embeddings[i] for i in group]
        survivor = max(group_risks, key=lambda r: len(r.text))
        survivor.merged_count = len(group_risks)
        for risk in group_risks:
            if risk.id != survivor.id:
                risk.status = "merged"
                merged_count += 1

    db.flush()
    return merged_count
