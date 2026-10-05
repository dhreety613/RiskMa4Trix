"""One-line risk titles. Template by default (LLM_ENABLED=false must
keep working - CLAUDE.md hard rule); an LLM may only polish the wording,
never decide the category or score.
"""

import re

from app.config import get_settings
from app.extract.classifier import Category


def _first_clause(text: str, max_len: int = 100) -> str:
    # Just the first sentence - splitting further on the first comma/
    # "and"/"or" cut titles down to "The Company's business" for
    # sentences whose subject is a long comma-separated list (common in
    # real 10-Ks: "Our business, reputation, results of operations...").
    first_sentence = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    clause = first_sentence.strip().rstrip(".")
    if len(clause) > max_len:
        clause = clause[:max_len].rsplit(" ", 1)[0] + "..."
    return clause


def template_title(text: str, category: Category | None) -> str:
    clause = _first_clause(text)
    if category is None:
        return clause
    return f"{category.name}: {clause}"


def _llm_title(text: str, category: Category | None) -> str | None:
    settings = get_settings()
    if not settings.llm_enabled or not settings.llm_api_key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=settings.llm_api_key)
        category_hint = f" (category: {category.name})" if category else ""
        prompt = (
            "Write a single short, plain-English title (under 12 words, no "
            "markdown) for this 10-K risk factor paragraph" + category_hint + ":\n\n"
            + text[:800]
        )
        response = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
        title = (response.text or "").strip().strip('"')
        return title or None
    except Exception:
        return None


def generate_title(text: str, category: Category | None) -> str:
    """Wording polish only - the fallback (template) is always correct
    and cheap; the LLM path is a nicer phrasing when enabled, never a
    source of truth for category or content.
    """
    return _llm_title(text, category) or template_title(text, category)
