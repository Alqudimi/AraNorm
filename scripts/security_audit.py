"""Measure regex behavior on adversarial inputs without mutating project data."""

from __future__ import annotations

import json
import time
from typing import Dict, List

from aranorm.utils.patterns import (
    ARABIZI_WORD_PATTERN,
    EMAIL_PATTERN,
    HASHTAG_PATTERN,
    HTML_PATTERN,
    MENTION_PATTERN,
    URL_PATTERN,
)

PATTERNS = {
    "url": URL_PATTERN,
    "email": EMAIL_PATTERN,
    "mention": MENTION_PATTERN,
    "hashtag": HASHTAG_PATTERN,
    "html": HTML_PATTERN,
    "arabizi": ARABIZI_WORD_PATTERN,
}


def measure(size: int) -> Dict[str, float]:
    text = ("<" * size) + ("@" * size) + ("#" * size) + ("a" * size)
    timings: Dict[str, float] = {}
    for name, pattern in PATTERNS.items():
        started = time.perf_counter()
        pattern.sub("", text)
        timings[name] = round(time.perf_counter() - started, 6)
    return timings


def main() -> None:
    sizes: List[int] = [1_000, 5_000, 10_000, 20_000]
    report = {str(size): measure(size) for size in sizes}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
