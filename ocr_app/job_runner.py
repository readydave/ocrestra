from __future__ import annotations

import datetime as dt
import importlib.metadata
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from queue import Full
from typing import Any

import psutil

try:
    from .config import LOG_ROOT, MAX_INPUT_FILE_BYTES, TEMP_ROOT
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import LOG_ROOT, MAX_INPUT_FILE_BYTES, TEMP_ROOT  # type: ignore


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


def _build_ocr_command(
    ocrmypdf_bin: str,
    input_pdf: Path,
    output_pdf: Path,
    force_ocr: bool,
    use_gpu: bool,
    optimize_for_size: bool,
    include_easyocr_plugin: bool,
) -> list[str]:
    cmd = [
        ocrmypdf_bin,
        "--jobs",
        "1",
        "--rotate-pages",
        "--deskew",
    ]
    if force_ocr:
        cmd.append("--force-ocr")
    else:
        cmd.append("--skip-text")
    if use_gpu:
        # EasyOCR plugin currently requires sandwich renderer (no hOCR support).
        cmd.extend(["--pdf-renderer", "sandwich"])
    else:
        cmd.extend(["--ocr-engine", "tesseract"])
    if optimize_for_size:
        cmd.extend(["-O", "2", "--jpeg-quality", "75", "--png-quality", "70"])
    if include_easyocr_plugin:
        cmd.extend(["--plugin", "ocrmypdf_easyocr"])
    cmd.extend([str(input_pdf), str(output_pdf)])
    return cmd


def _easyocr_plugin_autoregistered() -> bool:
    try:
        entry_points = importlib.metadata.entry_points()
        if hasattr(entry_points, "select"):
            ocrmypdf_plugins = entry_points.select(group="ocrmypdf")
        else:
            ocrmypdf_plugins = entry_points.get("ocrmypdf", [])
        for entry_point in ocrmypdf_plugins:
            value = getattr(entry_point, "value", "")
            if "ocrmypdf_easyocr" in value:
                return True
    except Exception:
        return False
    return False


def _is_easyocr_duplicate_registration_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "plugin already registered under a different name" in lowered
        and "ocrmypdf_easyocr" in lowered
    )


def _run_ocr(
    ocrmypdf_bin: str,
    input_pdf: Path,
    output_pdf: Path,
    force_ocr: bool,
    use_gpu: bool,
    optimize_for_size: bool,
) -> None:
    if output_pdf.exists():
        output_pdf.unlink()
    include_easyocr_plugin = use_gpu and not _easyocr_plugin_autoregistered()
    cmd = _build_ocr_command(
        ocrmypdf_bin,
        input_pdf,
        output_pdf,
        force_ocr,
        use_gpu=use_gpu,
        optimize_for_size=optimize_for_size,
        include_easyocr_plugin=include_easyocr_plugin,
    )
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("ocrmypdf executable is not available in PATH.") from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        if (
            use_gpu
            and include_easyocr_plugin
            and _is_easyocr_duplicate_registration_error(details)
        ):
            retry_cmd = _build_ocr_command(
                ocrmypdf_bin,
                input_pdf,
                output_pdf,
                force_ocr,
                use_gpu=use_gpu,
                optimize_for_size=optimize_for_size,
                include_easyocr_plugin=False,
            )
            subprocess.run(
                retry_cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return
        if details:
            raise RuntimeError(f"ocrmypdf failed with exit code {exc.returncode}: {details}") from exc
        raise RuntimeError(f"ocrmypdf failed with exit code {exc.returncode}.") from exc


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


def _is_path_within(base: Path, path: Path) -> bool:
    try:
        base_resolved = base.resolve()
        path_resolved = path.resolve()
    except Exception:
        return False
    return path_resolved == base_resolved or base_resolved in path_resolved.parents


def _safe_log_file(path: Path, task_id: str) -> Path:
    fallback = LOG_ROOT / "worker_logs" / f"{task_id}.log"
    try:
        if _is_path_within(LOG_ROOT, path.parent):
            return path
    except Exception:
        return fallback
    return fallback


def _safe_output_pdf(path: Path) -> Path:
    if path.suffix.lower() != ".pdf":
        raise ValueError("Output path must be a PDF.")
    if path.exists() and path.is_symlink():
        raise PermissionError("Refusing to overwrite symlink output file.")
    if path.parent.exists() and path.parent.is_symlink():
        raise PermissionError("Refusing symlink output directory.")
    return path


def run_ocr_job(config: dict[str, Any], queue_obj: Any) -> None:
    task_id = _sanitize_task_id(config.get("task_id", "task"))
    try:
        input_pdf = Path(config["input_pdf"])
        output_pdf = _safe_output_pdf(Path(config["output_pdf"]))
        log_file = _safe_log_file(Path(config["log_file"]), task_id)
        temp_dir = _safe_temp_dir(Path(config["temp_dir"]), task_id)
        force_ocr = bool(config.get("force_ocr", False))
        use_gpu = bool(config.get("use_gpu", False))
        optimize_for_size = bool(config.get("optimize_for_size", False))
    except Exception as exc:  # noqa: BLE001
        queue_obj.put(
            {
                "type": "done",
                "task_id": task_id,
                "success": False,
                "error": f"Invalid task configuration: {exc}",
                "output_pdf": "",
                "used_fallback": False,
                "duration_seconds": 0.0,
                "input_size": 0,
                "output_size": 0,
                "size_ratio": 0.0,
                "rss_start": 0,
                "rss_end": 0,
                "cpu_user_delta": 0.0,
                "cpu_system_delta": 0.0,
                "start_stamp": dt.datetime.now().isoformat(timespec="seconds"),
                "end_stamp": dt.datetime.now().isoformat(timespec="seconds"),
            }
        )
        return

    _configure_logging(log_file, queue_obj, task_id)
    logger = logging.getLogger("ocr_gui.worker")
    proc = psutil.Process(os.getpid())

    start = time.time()
    start_stamp = dt.datetime.now().isoformat(timespec="seconds")
    start_rss = proc.memory_info().rss
    start_cpu = proc.cpu_times()
    input_size = _safe_size(input_pdf)
    if input_size > MAX_INPUT_FILE_BYTES:
        error = (
            f"Input file is too large ({input_size} bytes). "
            f"Limit is {MAX_INPUT_FILE_BYTES} bytes."
        )
        queue_obj.put({"type": "status", "task_id": task_id, "status": "Failed"})
        queue_obj.put(
            {
                "type": "done",
                "task_id": task_id,
                "success": False,
                "error": error,
                "output_pdf": str(output_pdf),
                "used_fallback": False,
                "duration_seconds": 0.0,
                "input_size": input_size,
                "output_size": 0,
                "size_ratio": 0.0,
                "rss_start": start_rss,
                "rss_end": start_rss,
                "cpu_user_delta": 0.0,
                "cpu_system_delta": 0.0,
                "start_stamp": dt.datetime.now().isoformat(timespec="seconds"),
                "end_stamp": dt.datetime.now().isoformat(timespec="seconds"),
            }
        )
        return
    used_fallback = False

    logger.info("Task %s started.", task_id)
    logger.info("Input PDF: %s", input_pdf)
    logger.info("Output PDF: %s", output_pdf)
    logger.info("OCR mode: %s", "Force OCR all pages" if force_ocr else "Smart skip existing text")
    logger.info("OCR backend: %s", "EasyOCR GPU plugin" if use_gpu else "CPU defaults")
    logger.info(
        "Output size profile: %s",
        "Balanced compression (smaller output)" if optimize_for_size else "Standard",
    )
    queue_obj.put({"type": "status", "task_id": task_id, "status": "Running"})

    success = False
    error_message = ""
    ocrmypdf_bin = shutil.which("ocrmypdf")
    try:
        if not ocrmypdf_bin:
            error_message = "ocrmypdf command was not found in PATH."
            logger.error("%s", error_message)
            queue_obj.put({"type": "status", "task_id": task_id, "status": "Failed"})
        else:
            try:
                output_pdf.parent.mkdir(parents=True, exist_ok=True)
                _run_ocr(
                    ocrmypdf_bin,
                    input_pdf,
                    output_pdf,
                    force_ocr,
                    use_gpu,
                    optimize_for_size,
                )
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
                        _run_ocr(
                            ocrmypdf_bin,
                            temp_input,
                            temp_output,
                            force_ocr,
                            use_gpu,
                            optimize_for_size,
                        )
                        shutil.move(str(temp_output), str(output_pdf))
                        success = True
                    except Exception as fallback_exc:  # noqa: BLE001
                        error_message = f"{type(fallback_exc).__name__}: {fallback_exc}"
                        if use_gpu:
                            error_message += " GPU plugin failed; disable GPU Acceleration and retry on CPU."
                        logger.exception("Fallback OCR failed for %s: %s", input_pdf, fallback_exc)
                else:
                    error_message = f"{type(exc).__name__}: {exc}"
                    if use_gpu:
                        error_message += " GPU plugin failed; disable GPU Acceleration and retry on CPU."
                        logger.error(
                            "GPU plugin run failed. CUDA/plugin may be missing; retry with GPU disabled."
                        )
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
