from types import SimpleNamespace

from app.drift.matcher import match_filing_risks
from tests.test_dedupe import _unit_vector


def _risk(name: str, vector):
    """A plain duck-typed stand-in for a Risk ORM row - match_filing_risks
    only ever touches `.embedding_row.embedding`, so no real DB/session
    is needed for this purely algorithmic piece.
    """
    return SimpleNamespace(name=name, embedding_row=SimpleNamespace(embedding=vector))


def test_persisting_above_080_similarity():
    prev = [_risk("A", _unit_vector(1.0))]
    curr = [_risk("A'", _unit_vector(0.95))]

    matches = match_filing_risks(prev, curr)

    assert len(matches) == 1
    assert matches[0].label == "persisting"
    assert matches[0].prev_risk.name == "A"
    assert matches[0].curr_risk.name == "A'"


def test_reworded_between_065_and_080():
    prev = [_risk("A", _unit_vector(1.0))]
    curr = [_risk("A-reworded", _unit_vector(0.70))]

    matches = match_filing_risks(prev, curr)

    assert len(matches) == 1
    assert matches[0].label == "reworded"


def test_unrelated_risks_become_removed_and_new_not_forced_together():
    prev = [_risk("A", _unit_vector(1.0))]
    curr = [_risk("B", _unit_vector(0.0))]  # orthogonal - similarity 0

    matches = match_filing_risks(prev, curr)

    labels = sorted(m.label for m in matches)
    assert labels == ["new", "removed"]


def test_new_risk_with_no_prior_counterpart():
    prev = [_risk("A", _unit_vector(1.0))]
    curr = [_risk("A'", _unit_vector(0.95)), _risk("B", _unit_vector(0.0))]

    matches = match_filing_risks(prev, curr)

    labels = sorted(m.label for m in matches)
    assert labels == ["new", "persisting"]
    new_match = next(m for m in matches if m.label == "new")
    assert new_match.curr_risk.name == "B"


def test_removed_risk_with_no_successor():
    prev = [_risk("A", _unit_vector(1.0)), _risk("C", _unit_vector(0.0))]
    curr = [_risk("A'", _unit_vector(0.95))]

    matches = match_filing_risks(prev, curr)

    labels = sorted(m.label for m in matches)
    assert labels == ["persisting", "removed"]
    removed_match = next(m for m in matches if m.label == "removed")
    assert removed_match.prev_risk.name == "C"


def test_empty_prev_is_all_new():
    curr = [_risk("A", _unit_vector(1.0))]
    matches = match_filing_risks([], curr)
    assert len(matches) == 1
    assert matches[0].label == "new"


def test_empty_curr_is_all_removed():
    prev = [_risk("A", _unit_vector(1.0))]
    matches = match_filing_risks(prev, [])
    assert len(matches) == 1
    assert matches[0].label == "removed"


def test_both_empty_is_no_events():
    assert match_filing_risks([], []) == []
