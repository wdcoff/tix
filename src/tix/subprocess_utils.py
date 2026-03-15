"""Shared subprocess utilities.

Provides a sanitised environment dictionary for child processes,
stripping environment variables that match common secret patterns.
"""
from __future__ import annotations

import os

_SECRET_PATTERNS = {"TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL"}


def clean_env() -> dict[str, str]:
    """Return environment with sensitive vars stripped."""
    return {
        k: v for k, v in os.environ.items()
        if not any(pat in k.upper() for pat in _SECRET_PATTERNS)
    }
