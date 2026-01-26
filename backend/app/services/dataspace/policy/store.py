"""
Policy storage for dataspace policies.

Persists policy configs and ODRL documents to disk under the dataspace cache.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class PolicyStore:
    """Simple file-based policy store."""

    def __init__(self) -> None:
        settings = get_settings()
        base_dir = settings.dataspace_cache_dir
        self.policies_dir = Path(base_dir) / "policies"
        self.policies_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        policy_id: str,
        config: dict[str, Any],
        odrl: dict[str, Any],
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.utcnow().isoformat()
        record = {
            "policy_id": policy_id,
            "owner_id": owner_id,
            "config": config,
            "odrl": odrl,
            "created_at": now,
            "updated_at": now,
        }
        self._write(policy_id, record)
        return record

    def get(self, policy_id: str) -> dict[str, Any] | None:
        path = self._path(policy_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.warning("Failed to load policy %s: %s", policy_id, e)
            return None

    def update(
        self,
        policy_id: str,
        config: dict[str, Any],
        odrl: dict[str, Any],
    ) -> dict[str, Any] | None:
        record = self.get(policy_id)
        if record is None:
            return None
        record["config"] = config
        record["odrl"] = odrl
        record["updated_at"] = datetime.utcnow().isoformat()
        self._write(policy_id, record)
        return record

    def delete(self, policy_id: str) -> bool:
        path = self._path(policy_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list(self, owner_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for policy_path in self.policies_dir.glob("*.json"):
            try:
                record = json.loads(policy_path.read_text())
                if owner_id is not None and record.get("owner_id") != owner_id:
                    continue
                records.append(record)
            except Exception as e:
                logger.warning("Failed to read policy %s: %s", policy_path.name, e)
        records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return records[:limit]

    def _path(self, policy_id: str) -> Path:
        safe_id = policy_id.replace(":", "_").replace("/", "_")
        return self.policies_dir / f"{safe_id}.json"

    def _write(self, policy_id: str, record: dict[str, Any]) -> None:
        path = self._path(policy_id)
        path.write_text(json.dumps(record, indent=2))
