from __future__ import annotations

import tempfile
from pathlib import Path

APP_NAME = "OCRestra"
ORG_NAME = "OCRestra"
SETTINGS_APP = "OCRestra"

DEFAULT_WORKERS = 32
MAX_WORKERS = 64
MAX_QUEUE_ITEMS = 5000
MAX_DISCOVERED_PDFS = 20000
MAX_INPUT_FILE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB
MAX_SCAN_DEPTH = 24

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_ROOT = ROOT_DIR / "logs"
TEMP_ROOT = Path(tempfile.gettempdir()) / "ocr_gui_jobs"
