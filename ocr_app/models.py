from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskItem:
    task_id: str
    input_path: Path
    output_path: Path
    temp_dir: Path
    log_file: Path
    row: int
    status: str = "Queued"
    process: Any | None = None
    queue: Any | None = None
    ps_proc: Any | None = None
    used_fallback: bool = False
    peak_cpu_percent: float = 0.0
    peak_rss_bytes: int = 0
    progress_value: int = 0
    run_token: int = 0
    counted: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)
