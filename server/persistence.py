"""Snapshot do estado (quimico + historico) em disco, com write atomico
(escreve em .tmp e faz os.replace) pra nunca deixar o arquivo corrompido
se o processo morrer no meio da escrita."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def save(state: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def load(path: Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
