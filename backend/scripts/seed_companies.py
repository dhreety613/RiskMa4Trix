"""Seed the DB with a diverse set of ~25 tickers for the matrix/drift
dashboards to have something real to show. Run from backend/:

    python -m scripts.seed_companies
    python -m scripts.seed_companies --years 3 --tickers AAPL MSFT
"""

import argparse
import logging
import sys

from app.db import SessionLocal
from app.extract.pipeline import extract_for_company
from app.ingest.pipeline import TickerNotFound, ingest_company_full

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Deliberately spread across sectors so drift/matrix views aren't all
# "big tech" - tech, financials, healthcare, energy, industrials,
# consumer, utilities, materials.
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META",  # tech
    "JPM", "BAC", "GS",  # financials
    "JNJ", "PFE", "UNH",  # healthcare
    "XOM", "CVX",  # energy
    "BA", "CAT", "GE",  # industrials
    "KO", "PG", "MCD", "NKE",  # consumer
    "NEE", "DUK",  # utilities
    "LIN", "NEM",  # materials
    "DIS", "VZ",  # media/telecom
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--years", type=int, default=5)
    args = parser.parse_args()

    failures = []
    for ticker in args.tickers:
        db = SessionLocal()
        try:
            logger.info(f"Ingesting {ticker}...")
            company = ingest_company_full(db, ticker, years_back=args.years)
            logger.info(f"Extracting risks for {ticker}...")
            extract_for_company(db, company)
        except TickerNotFound:
            logger.error(f"{ticker}: no CIK found, skipping")
            failures.append(ticker)
        except Exception:
            logger.exception(f"{ticker}: ingestion failed")
            failures.append(ticker)
        finally:
            db.close()

    logger.info(f"Done. {len(args.tickers) - len(failures)}/{len(args.tickers)} succeeded.")
    if failures:
        logger.warning(f"Failed: {failures}")
        sys.exit(1)


if __name__ == "__main__":
    main()
