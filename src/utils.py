"""
Utility functions for file handling and processing.
"""

import logging

from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


def parse_pages(pages_arg: str) -> list[int]:
    """Parses a string of page ranges (e.g., '1-3, 5') into a list of 0-indexed page numbers."""
    pages = set()
    parts = pages_arg.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = map(int, part.split('-'))
            pages.update(range(start - 1, end))
        else:
            pages.add(int(part) - 1)
    return sorted(list(pages))
