from __future__ import annotations

import tempfile
from pathlib import Path

APP_NAME = "OCRestra"
ORG_NAME = "OCRestra"
SETTINGS_APP = "OCRestra"

DEFAULT_WORKERS = 32
MAX_WORKERS = 64

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_ROOT = ROOT_DIR / "logs"
TEMP_ROOT = Path(tempfile.gettempdir()) / "ocr_gui_jobs"
