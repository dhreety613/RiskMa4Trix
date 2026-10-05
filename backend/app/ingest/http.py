"""Shared HTTP client for SEC EDGAR: fair-access User-Agent, a hard rate
limit (SEC asks for <=10 req/s), and an on-disk cache so repeat ingests
(and local dev) don't re-hit SEC for data we already have.
"""

import hashlib
import json
import time
from pathlib import Path

import requests

from app.config import get_settings

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "edgar"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_MIN_INTERVAL = 1.0 / 10  # 10 req/s
_last_request_at = 0.0


def _throttle() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode()).hexdigest()
    return CACHE_DIR / f"{digest}.cache"


def fetch_text(url: str, use_cache: bool = True) -> str:
    cache_path = _cache_path(url)
    if use_cache and cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="ignore")

    _throttle()
    headers = {"User-Agent": get_settings().sec_user_agent}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    # EDGAR documents don't declare a charset in Content-Type. Most are
    # actually Windows-1252 (smart quotes etc as single bytes 0x91-0x97),
    # not UTF-8 - decoding those bytes as UTF-8 doesn't raise, it just
    # silently produces mojibake ("Company�s"). cp1252 is a full
    # single-byte codec (never raises), so try strict UTF-8 first and
    # only fall back to cp1252 when the bytes aren't valid UTF-8.
    try:
        text = resp.content.decode("utf-8")
    except UnicodeDecodeError:
        text = resp.content.decode("cp1252", errors="replace")

    if use_cache:
        cache_path.write_text(text, encoding="utf-8")
    return text


def fetch_json(url: str, use_cache: bool = True) -> dict:
    return json.loads(fetch_text(url, use_cache=use_cache))
