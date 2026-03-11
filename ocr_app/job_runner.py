from __future__ import annotations

import datetime as dt
import functools
import importlib.metadata
import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
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


class OCRCommandError(RuntimeError):
    def __init__(self, exit_code: int | None, details: str) -> None:
        self.exit_code = exit_code
        self.details = details.strip()
        if self.details and self.exit_code is not None:
            message = f"ocrmypdf failed with exit code {self.exit_code}: {self.details}"
        elif self.exit_code is not None:
            message = f"ocrmypdf failed with exit code {self.exit_code}."
        else:
            message = self.details or "ocrmypdf command failed."
        super().__init__(message)


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


@functools.lru_cache(maxsize=1)
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


def _detect_silent_easyocr_failure(details: str) -> str | None:
    lowered = details.lower()
    has_traceback = "traceback (most recent call last):" in lowered
    easyocr_context = (
        "ocrmypdf_easyocr" in lowered
        or "easyocr" in lowered
        or "downloading detection model" in lowered
        or "download_and_unzip" in lowered
    )
    network_failure = (
        "certificate_verify_failed" in lowered
        or "urllib.error.urlerror" in lowered
        or "ssl:" in lowered
    )
    if has_traceback and easyocr_context:
        if network_failure:
            return (
                "EasyOCR GPU backend could not download its model files. "
                "Check certificate trust/network access or retry on CPU."
            )
        return "EasyOCR GPU backend raised an internal error before OCR text was produced."
    return None


def _ocrmypdf_progress_bucket(message: str) -> int | None:
    if not message.startswith("Progress:"):
        return None
    match = re.search(r"(\d+(?:\.\d+)?)%", message)
    if match is None:
        return None
    try:
        return max(0, min(100, int(float(match.group(1)))))
    except Exception:
        return None


def _run_ocr_command(cmd: list[str]) -> None:
    logger = logging.getLogger("ocr_gui.worker")
    output_tail: list[str] = []
    output_tail_bytes = 0
    output_tail_limit = 16 * 1024
    last_progress_bucket: int | None = None

    def append_tail(chunk: str) -> None:
        nonlocal output_tail_bytes
        if not chunk:
            return
        output_tail.append(chunk)
        output_tail_bytes += len(chunk.encode("utf-8", errors="replace"))
        while output_tail and output_tail_bytes > output_tail_limit:
            dropped = output_tail.pop(0)
            output_tail_bytes -= len(dropped.encode("utf-8", errors="replace"))

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise OCRCommandError(None, "ocrmypdf executable is not available in PATH.") from exc

    if proc.stdout is not None:
        for line in proc.stdout:
            append_tail(line)
            message = line.rstrip()
            if message:
                progress_bucket = _ocrmypdf_progress_bucket(message)
                if progress_bucket is not None:
                    if progress_bucket == last_progress_bucket:
                        continue
                    last_progress_bucket = progress_bucket
                logger.info("ocrmypdf | %s", message)

    rc = proc.wait()
    details = "".join(output_tail).strip()
    if rc != 0:
        raise OCRCommandError(rc, details)
    silent_failure = _detect_silent_easyocr_failure(details)
    if silent_failure:
        raise OCRCommandError(None, f"{silent_failure}\n{details}".strip())


def _is_gpu_related_failure(details: str) -> bool:
    lowered = details.lower()
    markers = (
        "ocrmypdf_easyocr",
        "easyocr",
        "cuda",
        "torch.cuda",
        "gpu",
        "plugin already registered under a different name",
        "no module named 'ocrmypdf_easyocr'",
    )
    return any(marker in lowered for marker in markers)


def _is_input_file_error(details: str) -> bool:
    lowered = details.lower()
    return "inputfileerror" in lowered or "input file error" in lowered


def _format_ocr_error(error: OCRCommandError) -> str:
    if _is_input_file_error(error.details):
        return (
            "InputFileError: OCRmyPDF could not process this PDF "
            "(file may be damaged, encrypted, or malformed)."
        )
    return str(error)


def _run_with_gpu_retry(
    ocrmypdf_bin: str,
    input_pdf: Path,
    output_pdf: Path,
    force_ocr: bool,
    use_gpu: bool,
    optimize_for_size: bool,
    logger: logging.Logger,
) -> bool:
    try:
        _run_ocr(
            ocrmypdf_bin,
            input_pdf,
            output_pdf,
            force_ocr,
            use_gpu,
            optimize_for_size,
        )
        return False
    except OCRCommandError as exc:
        if use_gpu and _is_gpu_related_failure(exc.details):
            logger.warning("GPU backend failed. Retrying this file once with CPU backend.")
            try:
                _run_ocr(
                    ocrmypdf_bin,
                    input_pdf,
                    output_pdf,
                    force_ocr,
                    False,
                    optimize_for_size,
                )
                logger.info("CPU fallback after GPU failure succeeded.")
                return True
            except OCRCommandError:
                logger.error("CPU fallback after GPU failure also failed.")
                raise
        raise


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
        _run_ocr_command(cmd)
    except OCRCommandError as exc:
        details = exc.details
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
            _run_ocr_command(retry_cmd)
            return
        raise


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


def _has_symlink_segment(path: Path) -> bool:
    probe = Path(path.anchor) if path.is_absolute() else Path.cwd()
    for segment in path.parts:
        if segment in {"", path.anchor}:
            continue
        probe = probe / segment
        try:
            if probe.is_symlink():
                return True
        except Exception:
            return True
    return False


def _safe_output_pdf(path: Path) -> Path:
    if path.suffix.lower() != ".pdf":
        raise ValueError("Output path must be a PDF.")
    if path.is_symlink():
        raise PermissionError("Refusing to overwrite symlink output file.")
    if _has_symlink_segment(path.parent):
        raise PermissionError("Refusing symlink output directory path.")
    return path


def _ensure_safe_output_dir(path: Path) -> Path:
    if _has_symlink_segment(path):
        raise PermissionError("Refusing symlink output directory path.")
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or _has_symlink_segment(path):
        raise PermissionError("Refusing symlink output directory path.")
    return path


def _copy_file_to_fd(src: Path, dest_fd: int) -> None:
    with src.open("rb") as src_handle, os.fdopen(dest_fd, "wb") as dest_handle:
        shutil.copyfileobj(src_handle, dest_handle)
        dest_handle.flush()
        os.fsync(dest_handle.fileno())


def _install_output_pdf_generic(staged_output: Path, output_pdf: Path) -> None:
    output_dir = _ensure_safe_output_dir(output_pdf.parent)
    temp_fd, temp_name = tempfile.mkstemp(
        prefix=".ocrestra-",
        suffix=".tmp",
        dir=output_dir,
    )
    temp_path = Path(temp_name)
    try:
        _copy_file_to_fd(staged_output, temp_fd)
        if output_pdf.is_symlink():
            raise PermissionError("Refusing to overwrite symlink output file.")
        os.replace(temp_path, output_pdf)
    except Exception:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        raise


def _install_output_pdf_posix(staged_output: Path, output_pdf: Path) -> None:
    output_dir = _ensure_safe_output_dir(output_pdf.parent)
    dir_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        dir_flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        dir_flags |= os.O_CLOEXEC
    dir_fd = os.open(output_dir, dir_flags)
    temp_name = f".ocrestra-{os.getpid()}-{time.time_ns()}.tmp"
    temp_fd: int | None = None
    try:
        temp_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            temp_flags |= os.O_NOFOLLOW
        temp_fd = os.open(temp_name, temp_flags, 0o600, dir_fd=dir_fd)
        _copy_file_to_fd(staged_output, temp_fd)
        temp_fd = None
        try:
            current = os.stat(output_pdf.name, dir_fd=dir_fd, follow_symlinks=False)
        except FileNotFoundError:
            current = None
        if current is not None and stat.S_ISLNK(current.st_mode):
            raise PermissionError("Refusing to overwrite symlink output file.")
        os.replace(temp_name, output_pdf.name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        try:
            os.fsync(dir_fd)
        except OSError:
            pass
    except Exception:
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        try:
            os.unlink(temp_name, dir_fd=dir_fd)
        except FileNotFoundError:
            pass
        except OSError:
            pass
        raise
    finally:
        os.close(dir_fd)


def _install_output_pdf(staged_output: Path, output_pdf: Path) -> None:
    output_pdf = _safe_output_pdf(output_pdf)
    if not staged_output.exists() or staged_output.is_symlink():
        raise FileNotFoundError(f"Staged output is missing or unsafe: {staged_output}")
    if os.name != "nt":
        _install_output_pdf_posix(staged_output, output_pdf)
        return
    _install_output_pdf_generic(staged_output, output_pdf)


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
    used_cpu_fallback = False
    ocrmypdf_bin = shutil.which("ocrmypdf")
    staged_output = temp_dir / f"{task_id}_output.pdf"
    try:
        if not ocrmypdf_bin:
            error_message = "ocrmypdf command was not found in PATH."
            logger.error("%s", error_message)
            queue_obj.put({"type": "status", "task_id": task_id, "status": "Failed"})
        else:
            temp_dir.mkdir(parents=True, exist_ok=True)
            try:
                used_cpu_fallback = _run_with_gpu_retry(
                    ocrmypdf_bin,
                    input_pdf,
                    staged_output,
                    force_ocr,
                    use_gpu,
                    optimize_for_size,
                    logger,
                )
                _install_output_pdf(staged_output, output_pdf)
                success = True
            except OCRCommandError as exc:
                if _should_fallback_to_tmp(input_pdf, exc):
                    try:
                        used_fallback = True
                        logger.warning("Permission/mount issue detected. Retrying via %s", temp_dir)
                        temp_dir.mkdir(parents=True, exist_ok=True)
                        temp_input = temp_dir / input_pdf.name
                        temp_output = temp_dir / f"{task_id}_fallback_output.pdf"
                        shutil.copy2(input_pdf, temp_input)
                        used_cpu_fallback = _run_with_gpu_retry(
                            ocrmypdf_bin,
                            temp_input,
                            temp_output,
                            force_ocr,
                            use_gpu,
                            optimize_for_size,
                            logger,
                        )
                        _install_output_pdf(temp_output, output_pdf)
                        success = True
                    except OCRCommandError as fallback_exc:
                        error_message = _format_ocr_error(fallback_exc)
                        if _is_input_file_error(fallback_exc.details):
                            logger.error("Input file appears invalid/unreadable for OCRmyPDF: %s", input_pdf)
                        else:
                            logger.exception("Fallback OCR failed for %s: %s", input_pdf, fallback_exc)
                    except Exception as fallback_exc:  # noqa: BLE001
                        error_message = f"{type(fallback_exc).__name__}: {fallback_exc}"
                        logger.exception("Fallback OCR failed for %s: %s", input_pdf, fallback_exc)
                else:
                    error_message = _format_ocr_error(exc)
                    if _is_input_file_error(exc.details):
                        logger.error("Input file appears invalid/unreadable for OCRmyPDF: %s", input_pdf)
                    else:
                        logger.exception("OCR failed for %s: %s", input_pdf, exc)
            except Exception as exc:  # noqa: BLE001
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
        if used_cpu_fallback:
            logger.info("Used CPU retry after GPU failure: yes")

        queue_obj.put(
            {
                "type": "done",
                "task_id": task_id,
                "success": success,
                "error": error_message,
                "output_pdf": str(output_pdf),
                "used_fallback": used_fallback,
                "used_cpu_fallback": used_cpu_fallback,
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
