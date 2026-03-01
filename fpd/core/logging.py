# fpd/core/logging.py
from __future__ import annotations

import logging
from typing import Optional


_LOGGER_NAME = "fpd"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Returns a configured logger.
    In Streamlit, logs go to the terminal running the app.
    """
    logger = logging.getLogger(name or _LOGGER_NAME)

    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
