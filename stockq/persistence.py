from __future__ import annotations

import json
import os
import threading
from pathlib import Path


class JsonWatchlistStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("STOCKQ_WATCHLIST_PATH", ".stockq/watchlist.json")
        self.path = Path(configured)
        self._lock = threading.Lock()

    def list_items(self) -> list[dict[str, object]]:
        with self._lock:
            if not self.path.exists():
                return []
            try:
                content = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Could not read watchlist {self.path}: {exc}") from exc
        if not isinstance(content, list) or any(not isinstance(item, dict) for item in content):
            raise RuntimeError(f"Watchlist {self.path} has an invalid format.")
        return content

    def add(self, symbol: str, period: str, horizon: int) -> None:
        items = self.list_items()
        updated = False
        for item in items:
            if item.get("symbol") == symbol:
                item.update({"period": period, "horizon": horizon})
                updated = True
                break
        if not updated:
            items.append({"symbol": symbol, "period": period, "horizon": horizon})
        self._write(items)

    def remove(self, symbol: str) -> None:
        self._write([item for item in self.list_items() if item.get("symbol") != symbol])

    def _write(self, items: list[dict[str, object]]) -> None:
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
                temp_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
                temp_path.replace(self.path)
            except OSError as exc:
                raise RuntimeError(f"Could not save watchlist {self.path}: {exc}") from exc
