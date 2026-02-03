from __future__ import annotations

import datetime as dt
import logging
import os
import re
import shutil
import time
from pathlib import Path
from queue import Full
from typing import Any

import ocrmypdf
import psutil

try:
    from .config import TEMP_ROOT
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import TEMP_ROOT  # type: ignore


class QueueLogHandler(logging.Handler):
    def __init__(self, queue_obj: Any, task_id: str) -> None:
        super().__init__()
        self.queue_obj = queue_obj
        self.task_id = task_id

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            return
        payload = {"type": "log", "task_id": self.task_id, "message": message}
        try:
            self.queue_obj.put_nowait(payload)
        except Full:
            pass
        except Exception:
            pass


def _configure_logging(log_file: Path, queue_obj: Any, task_id: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
        "%H:%M:%S",
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    queue_handler = QueueLogHandler(queue_obj, task_id)
    queue_handler.setFormatter(formatter)
    root.addHandler(queue_handler)

    logging.getLogger("ocrmypdf").setLevel(logging.INFO)


def _run_ocr(input_pdf: Path, output_pdf: Path, force_ocr: bool) -> None:
    if output_pdf.exists():
        output_pdf.unlink()
    ocrmypdf.ocr(
        str(input_pdf),
        str(output_pdf),
        jobs=1,
        progress_bar=False,
        rotate_pages=True,
        deskew=True,
        skip_text=not force_ocr,
        force_ocr=force_ocr,
    )


def _should_fallback_to_tmp(pdf_path: Path, exc: Exception) -> bool:
    if not str(pdf_path).startswith("/mnt/"):
        return False
    if isinstance(exc, PermissionError):
        return True
    markers = (
        "permission",
        "operation not permitted",
        "read-only file system",
        "access denied",
        "mount",
    )
    message = str(exc).lower()
    return any(marker in message for marker in markers)


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0


def _cleanup_temp_dir(temp_dir: Path) -> None:
    try:
        resolved = temp_dir.resolve()
        temp_root = TEMP_ROOT.resolve()
        if resolved != temp_root and temp_root not in resolved.parents:
            return
    except Exception:
        return
    shutil.rmtree(temp_dir, ignore_errors=True)


def _sanitize_task_id(value: Any) -> str:
    task_id = str(value)
    if re.fullmatch(r"[a-f0-9]{8,32}", task_id):
        return task_id
    return "task"


def _safe_temp_dir(path: Path, task_id: str) -> Path:
    fallback = TEMP_ROOT / task_id
    try:
        resolved = path.resolve()
        temp_root = TEMP_ROOT.resolve()
        if resolved == temp_root or temp_root in resolved.parents:
            return resolved
    except Exception:
        return fallback
    return fallback


def run_ocr_job(config: dict[str, Any], queue_obj: Any) -> None:
    task_id = _sanitize_task_id(config.get("task_id", "task"))
    input_pdf = Path(config["input_pdf"])
    output_pdf = Path(config["output_pdf"])
    log_file = Path(config["log_file"])
    temp_dir = _safe_temp_dir(Path(config["temp_dir"]), task_id)
    force_ocr = bool(config.get("force_ocr", False))

    _configure_logging(log_file, queue_obj, task_id)
    logger = logging.getLogger("ocr_gui.worker")
    proc = psutil.Process(os.getpid())

    start = time.time()
    start_stamp = dt.datetime.now().isoformat(timespec="seconds")
    start_rss = proc.memory_info().rss
    start_cpu = proc.cpu_times()
    input_size = _safe_size(input_pdf)
    used_fallback = False

    logger.info("Task %s started.", task_id)
    logger.info("Input PDF: %s", input_pdf)
    logger.info("Output PDF: %s", output_pdf)
    logger.info("OCR mode: %s", "Force OCR all pages" if force_ocr else "Smart skip existing text")
    queue_obj.put({"type": "status", "task_id": task_id, "status": "Running"})

    success = False
    error_message = ""
    try:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        _run_ocr(input_pdf, output_pdf, force_ocr)
        success = True
    except Exception as exc:  # noqa: BLE001
        if _should_fallback_to_tmp(input_pdf, exc):
            try:
                used_fallback = True
                logger.warning("Permission/mount issue detected. Retrying via %s", temp_dir)
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_input = temp_dir / input_pdf.name
                temp_output = temp_dir / f"{input_pdf.stem}_ocr.pdf"
                shutil.copy2(input_pdf, temp_input)
                _run_ocr(temp_input, temp_output, force_ocr)
                shutil.move(str(temp_output), str(output_pdf))
                success = True
            except Exception as fallback_exc:  # noqa: BLE001
                error_message = f"{type(fallback_exc).__name__}: {fallback_exc}"
                logger.exception("Fallback OCR failed for %s: %s", input_pdf, fallback_exc)
        else:
            error_message = f"{type(exc).__name__}: {exc}"
            logger.exception("OCR failed for %s: %s", input_pdf, exc)
    finally:
        duration = time.time() - start
        end_stamp = dt.datetime.now().isoformat(timespec="seconds")
        end_rss = proc.memory_info().rss
        end_cpu = proc.cpu_times()
        output_size = _safe_size(output_pdf) if success else 0
        ratio = (output_size / input_size) if input_size else 0.0

        logger.info("Task start: %s", start_stamp)
        logger.info("Task end: %s", end_stamp)
        logger.info("Duration: %.2f seconds", duration)
        logger.info("Input size: %d bytes", input_size)
        logger.info("Output size: %d bytes", output_size)
        logger.info("Output/Input size ratio: %.4f", ratio)
        logger.info("Process RSS start: %d bytes", start_rss)
        logger.info("Process RSS end: %d bytes", end_rss)
        logger.info("Process CPU user delta: %.4f", end_cpu.user - start_cpu.user)
        logger.info("Process CPU system delta: %.4f", end_cpu.system - start_cpu.system)
        if used_fallback:
            logger.info("Used /tmp fallback: yes")

        queue_obj.put(
            {
                "type": "done",
                "task_id": task_id,
                "success": success,
                "error": error_message,
                "output_pdf": str(output_pdf),
                "used_fallback": used_fallback,
                "duration_seconds": duration,
                "input_size": input_size,
                "output_size": output_size,
                "size_ratio": ratio,
                "rss_start": start_rss,
                "rss_end": end_rss,
                "cpu_user_delta": end_cpu.user - start_cpu.user,
                "cpu_system_delta": end_cpu.system - start_cpu.system,
                "start_stamp": start_stamp,
                "end_stamp": end_stamp,
            }
        )
        _cleanup_temp_dir(temp_dir)


if __name__ == "__main__":
    print("job_runner.py is an internal worker module.")
    print("Launch the app with: python -m ocr_app")
    raise SystemExit(0)
