"""配置与操作记录的本地存储。

位置：%APPDATA%\\VideoRenumber\\
- config.json   已添加的文件夹列表与当前选择
- history\\      每个文件夹最近一次重命名的新旧对照，用于撤销
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "VideoRenumber"
CONFIG_PATH = APP_DIR / "config.json"
HISTORY_DIR = APP_DIR / "history"

DEFAULT_CONFIG = {"folders": [], "selected": None, "names": {}, "start": 1}


def load_config() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"folders": [], "selected": None, "names": {}, "start": 1}
    folders = [str(p) for p in data.get("folders", []) if isinstance(p, str)]
    selected = data.get("selected")
    if selected not in folders:
        selected = folders[0] if folders else None
    raw_names = data.get("names")
    names = {}
    if isinstance(raw_names, dict):
        names = {k: v for k, v in raw_names.items() if isinstance(k, str) and isinstance(v, str)}
    start = data.get("start", 1)
    if not isinstance(start, int) or isinstance(start, bool) or start < 0:
        start = 1
    return {"folders": folders, "selected": selected, "names": names, "start": start}


def save_config(
    folders: list[str],
    selected: str | None,
    names: dict[str, str] | None = None,
    start: int = 1,
) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    names = names or {}
    payload = {
        "folders": list(folders),
        "selected": selected,
        "names": {folder: names[folder] for folder in folders if folder in names},
        "start": start,
    }
    CONFIG_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _key(folder: str | Path) -> str:
    normalized = os.path.normcase(os.path.abspath(str(folder)))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _history_path(folder: str | Path) -> Path:
    return HISTORY_DIR / f"{_key(folder)}.json"


def record_history(folder: str | Path, pairs: list[tuple[str, str]]) -> None:
    """pairs 为 (原文件名, 新文件名)。"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "folder": str(folder),
        "time": datetime.now().isoformat(timespec="seconds"),
        "pairs": [[old, new] for old, new in pairs],
    }
    _history_path(folder).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_history(folder: str | Path) -> dict | None:
    try:
        data = json.loads(_history_path(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pairs = data.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        return None
    return data


def clear_history(folder: str | Path) -> None:
    try:
        _history_path(folder).unlink()
    except OSError:
        pass
