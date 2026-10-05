"""Smoke test only - real accuracy numbers come from
scripts/eval_classifier.py against hand labels (see docs/VALIDATION.md),
not from eyeballing a couple of obvious examples here. This just confirms
the embedding/classification machinery isn't broken.
"""

from app.extract.classifier import classify_text


def test_obvious_cybersecurity_paragraph_classifies_correctly():
    text = (
        "A cybersecurity breach could result in unauthorized access to our "
        "systems and theft of confidential customer data, exposing us to "
        "significant liability and reputational harm."
    )
    result = classify_text(text)
    assert result.category_slug == "cybersecurity"
    assert result.confidence > 0.5


def test_gibberish_is_unclassified():
    result = classify_text("asdf qwerty zzz 12345 lorem ipsum nonsense")
    assert result.category_slug is None
