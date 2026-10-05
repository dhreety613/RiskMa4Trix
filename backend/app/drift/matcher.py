"""Matches risks between two consecutive filings of the SAME company by
embedding similarity, using the Hungarian algorithm (optimal 1:1
assignment, not greedy nearest-neighbor) so one risk can't "steal" the
best match for two different risks in the other filing.

Labels (thresholds per CLAUDE.md's source spec):
  similarity >= 0.80           -> persisting (same risk, same wording)
  0.65 <= similarity < 0.80    -> reworded    (same risk, reworded)
  below 0.65, or unmatched     -> that risk counts as removed (prev
                                   side) / new (curr side) instead -
                                   forcing a low-confidence match would
                                   be worse than reporting them as
                                   unrelated.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.extract.classifier import _normalize
from app.models import Risk

PERSISTING_THRESHOLD = 0.80
REWORDED_THRESHOLD = 0.65


@dataclass
class DriftMatch:
    label: str  # new | removed | persisting | reworded
    prev_risk: Risk | None
    curr_risk: Risk | None
    similarity: float | None


def match_filing_risks(prev_risks: list[Risk], curr_risks: list[Risk]) -> list[DriftMatch]:
    if not prev_risks and not curr_risks:
        return []
    if not prev_risks:
        return [DriftMatch("new", None, r, None) for r in curr_risks]
    if not curr_risks:
        return [DriftMatch("removed", r, None, None) for r in prev_risks]

    prev_with_emb = [r for r in prev_risks if r.embedding_row]
    curr_with_emb = [r for r in curr_risks if r.embedding_row]
    # Risks without an embedding (shouldn't normally happen - extraction
    # always writes one - but don't let a data gap crash drift) can't be
    # matched at all; they fall straight to removed/new.
    events: list[DriftMatch] = [
        DriftMatch("removed", r, None, None) for r in prev_risks if r not in prev_with_emb
    ]
    events += [DriftMatch("new", None, r, None) for r in curr_risks if r not in curr_with_emb]
    if not prev_with_emb or not curr_with_emb:
        events += [DriftMatch("removed", r, None, None) for r in prev_with_emb]
        events += [DriftMatch("new", None, r, None) for r in curr_with_emb]
        return events

    prev_vectors = _normalize(
        np.array([r.embedding_row.embedding for r in prev_with_emb], dtype=np.float32)
    )
    curr_vectors = _normalize(
        np.array([r.embedding_row.embedding for r in curr_with_emb], dtype=np.float32)
    )
    similarity = prev_vectors @ curr_vectors.T

    row_idx, col_idx = linear_sum_assignment(-similarity)

    matched_prev: set[int] = set()
    matched_curr: set[int] = set()
    for i, j in zip(row_idx, col_idx, strict=True):
        sim = float(similarity[i, j])
        if sim < REWORDED_THRESHOLD:
            continue  # too different to call the same risk - leave unmatched
        label = "persisting" if sim >= PERSISTING_THRESHOLD else "reworded"
        events.append(DriftMatch(label, prev_with_emb[i], curr_with_emb[j], sim))
        matched_prev.add(i)
        matched_curr.add(j)

    events += [
        DriftMatch("removed", r, None, None)
        for i, r in enumerate(prev_with_emb)
        if i not in matched_prev
    ]
    events += [
        DriftMatch("new", None, r, None)
        for j, r in enumerate(curr_with_emb)
        if j not in matched_curr
    ]
    return events
