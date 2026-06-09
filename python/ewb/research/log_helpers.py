"""Logging helpers for research scripts."""
from __future__ import annotations


def log_processing_error(ticker: str, interval: str, exc: Exception,
                         context: str = "pipeline") -> None:
    """Print a compact, grep-friendly processing error."""
    print(f"[skip:{context}] {ticker} {interval}: {type(exc).__name__}: {exc}")
