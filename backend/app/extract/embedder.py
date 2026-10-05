"""Thin wrapper around fastembed so the rest of the app imports one
function instead of knowing about the ONNX model directly. Shared by the
classifier (taxonomy + risk paragraphs), dedupe (clean/dedupe.py), and
drift matching (drift/matcher.py) - all need the same 384-dim space.
"""

from functools import lru_cache

import numpy as np

from app.config import get_settings


@lru_cache
def _get_model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=get_settings().embedding_model)


def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    model = _get_model()
    return np.array(list(model.embed(texts)), dtype=np.float32)


def embed_text(text: str) -> np.ndarray:
    return embed_texts([text])[0]
