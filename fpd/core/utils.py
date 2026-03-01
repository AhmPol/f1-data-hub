# fpd/core/utils.py
from __future__ import annotations

from pathlib import Path
from typing import Any
import re


def ensure_dir(path: str) -> str:
    """
    Create dir if missing; return normalized path.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def safe_str(x: Any) -> str:
    """
    Converts unknown values into a safe, trimmed string.
    """
    if x is None:
        return ""
    return str(x).strip()


def slugify(text: str) -> str:
    """
    Make a filesystem-safe slug.
    """
    text = safe_str(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")
