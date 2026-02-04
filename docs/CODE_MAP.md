# OCRestra Code Map

This is the developer-facing map of where behavior lives in code.

## Entry Points

- `ocr_gui.py`
  - Thin wrapper script that calls package entrypoint.
- `ocr_app/__main__.py`
  - Sets multiprocessing start method and runs `run_app()`.

## Core Modules

- `ocr_app/ui.py`
  - `DropZone`: drag-and-drop widget for files/folders.
  - `MainWindow`: main app controller (UI composition + job orchestration).
  - Owns queue table, metrics, progress updates, menu actions, and persistence.

- `ocr_app/job_runner.py`
  - Worker process logic for one OCR task.
  - Configures logging, runs OCRmyPDF, reports events/metrics back to UI.
  - Handles `/mnt` fallback-to-temp behavior.

- `ocr_app/models.py`
  - `TaskItem` dataclass used as single source of truth for per-file state.

- `ocr_app/config.py`
  - App constants, queue/safety limits, and common paths.

- `ocr_app/themes.py`
  - Applies `system`/`dark`/`light` theme palettes and style sheets.

## Main Execution Flow

1. `run_app()` creates `QApplication` and `MainWindow`.
2. User adds files/folders via drag/drop or picker controls.
3. UI resolves inputs to PDFs and creates `TaskItem` rows.
4. `Start OCR` schedules tasks and spawns worker processes.
5. Workers emit log/status/done events through multiprocessing queues.
6. UI timer polls queues, updates statuses/progress/logs/metrics.
7. Completed jobs unlock row actions (`Open Folder`, `View Log`).

## State Ownership

- Per-file runtime state: `TaskItem` in `MainWindow.tasks`.
- Fast lookup by input path: `MainWindow.path_to_task`.
- Log lines displayed in UI: `MainWindow.log_entries`.
- User settings and remembered options: Qt `QSettings`.
- Session restore state file: `QStandardPaths.AppConfigLocation`.

## Security-Relevant Code Areas

- Queue and scan limits: `ocr_app/config.py` + checks in `ui.py`.
- Output/temp path safety:
  - `ui.py`: `_next_output_path`, `_cleanup_task_files`, `_is_path_within`
  - `job_runner.py`: `_safe_output_pdf`, `_safe_temp_dir`, `_safe_log_file`
- Custom command validation:
  - `ui.py`: `_validate_custom_file_manager_template`
- CI checks:
  - `.github/workflows/security.yml` (Gitleaks + pip-audit)

## Where to Change Common Features

- Add control/menu item: `MainWindow._build_ui()` / `MainWindow._build_menus()`
- Persist new setting: `MainWindow.__init__()` + `closeEvent()` + restore/save helpers
- Change OCR behavior: `job_runner.py` (`_run_ocr`, fallback logic)
- Change progress/status logic: `ui.py` (`_set_progress`, `_finalize_task`, `_update_batch_progress`)
- Add per-task metric: worker done payload + `TaskItem.metrics` handling in UI
