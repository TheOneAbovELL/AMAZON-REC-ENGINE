"""Optional append-only JSON-lines log of recommendation requests (QUERY_LOG_PATH).

Disabled unless QUERY_LOG_PATH is set: queries typed by shoppers can contain personal
information, so logging them is an explicit operator decision.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


class QueryLog:
    def __init__(self, path: Path | None):
        self.path = path
        self._lock = threading.Lock()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, response: dict) -> None:
        if self.path is None:
            return
        results = response.get("results", [])
        record = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "query": response.get("query"),
            "profile": response.get("profile"),
            "mode": response.get("engine", {}).get("mode"),
            "total_matches": response.get("total_matches"),
            "results": [r["asin"] for r in results],
            "top_score": results[0]["score"] if results else None,
            "took_ms": response.get("took_ms"),
        }
        try:
            with self._lock, self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            log.warning("Could not write query log to %s", self.path, exc_info=True)
