"""Online SQLite backup endpoint — consistent copy while the API serves.

POST /api/admin/backup (write-auth required): writes a consistent snapshot of
the database to a timestamped file under LOGICFORGE_BACKUP_DIR (default ./backups)
and reports the file name. For cron-based backups call this endpoint on a schedule.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from logicforge_api import auth
from logicforge_api.persistence import connect, write_lock

router = APIRouter(prefix="/api/admin", tags=["admin"])

BACKUP_DIR = os.environ.get("LOGICFORGE_BACKUP_DIR", "./backups")


@router.post("/backup")
def backup_endpoint(_auth: None = Depends(auth.require_write_auth)) -> dict[str, Any]:
    """Create a consistent online backup of the SQLite database."""
    target_dir = Path(BACKUP_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = target_dir / f"logicforge-backup-{stamp}.db"
    source = connect()
    sink = sqlite3.connect(str(target))
    with write_lock():
        source.backup(sink)
    sink.close()
    return {"backup": str(target), "bytes": target.stat().st_size, "created_at": stamp}
