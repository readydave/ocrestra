# OCRestra Architecture

## High-Level Design

OCRestra is a desktop GUI app with a process-based OCR backend:

- UI layer: PySide6 window, queue table, controls, logs, and metrics.
- Worker layer: separate process per file running OCRmyPDF.
- Coordination: multiprocessing queue events polled by UI timer.

This isolates long-running OCR work and allows hard cancel via process termination.

## Main Components

- `ocr_app/ui.py`
  - `MainWindow` owns queue state, controls, scheduling, table updates, and logs.
  - `DropZone` handles drag-and-drop UX.
- `ocr_app/job_runner.py`
  - Worker entry that configures logging, executes OCR, emits completion metrics.
- `ocr_app/models.py`
  - `TaskItem` dataclass for per-job state.
- `ocr_app/config.py`
  - App constants, temp and log root paths.
- `ocr_app/__main__.py`
  - Package entrypoint (`python -m ocr_app`).
- `ocr_gui.py`
  - Thin script wrapper delegating to package entrypoint.

## Data Flow

1. User adds files/folders.
2. UI expands folders to PDFs and adds `TaskItem` rows.
3. `Start OCR` computes parallelism and starts worker processes.
4. Worker emits log/status/done events to multiprocessing queue.
5. UI timer drains queues, updates progress and table state.
6. Completion updates metrics/log summaries and action buttons.

## Worker Event Protocol

Messages sent from worker to UI queue:

- `{"type": "log", "task_id": ..., "message": ...}`
- `{"type": "status", "task_id": ..., "status": "Running"}`
- `{"type": "done", "task_id": ..., "success": bool, ...metrics...}`

## Filesystem Strategy

- Logs: `logs/<batch_id>/<file>_<task_id>.log`
- Temp: `<system_temp>/ocr_gui_jobs/<task_id>`
- Output: `<input_parent>/OCR_Output/<original_name>.pdf`
- `/mnt` failures trigger temp staging fallback.

## Safety and Hardening Notes

- Queue restore validates state file and limits restore volume.
- Custom file manager templates are validated and constrained.
- Folder scanning avoids symlink-directory traversal.
- Temp cleanup constrained to configured temp root.

## UI Threading Model

- No blocking OCR work in GUI thread.
- UI uses timers for:
  - worker queue polling,
  - periodic metrics refresh,
  - periodic queue state save.
