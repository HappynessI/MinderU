from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable


def stable_id(*parts: str, length: int = 16) -> str:
    raw = "||".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:length]


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, value: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_command(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def normalize_space(text: str) -> str:
    text = text.replace("\x0c", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def list_input_files(path: str | Path, suffixes: tuple[str, ...]) -> list[Path]:
    p = Path(path)
    if p.is_file():
        return [p] if p.suffix.lower() in suffixes else []
    return sorted(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in suffixes)

