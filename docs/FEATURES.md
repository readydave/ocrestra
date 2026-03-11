# OCRestra Features

## Queue Ingestion

- Drag-and-drop accepts PDF files and folders.
- Folder import mode is selectable per add operation:
  - recursive scan (all subfolders)
  - top-level only (selected folder only)
- PDF matching is case-insensitive.
- Symlink directory traversal is disabled during folder walk.
- Duplicate files are de-duplicated per queue by normalized path and, when available, filesystem identity (`st_dev`, `st_ino`).
- Queue and discovery limits:
  - max queued files: `5000`
  - max discovered PDFs per add operation: `20000`
  - max scan depth: `24`
  - max accepted input file size: `2 GiB`

## OCR Execution Engine

- OCR processing executes OCRmyPDF CLI in each worker process via validated argument lists (`Popen`, no shell mode).
- Each queued file runs in its own Python multiprocessing worker.
- UI remains non-blocking while jobs run.
- Cancel actions terminate worker processes immediately.
- Runtime check verifies `ocrmypdf` exists in `PATH` before processing.
- Worker streams OCR output to logs incrementally instead of buffering full command output in memory.
- GPU EasyOCR tracebacks during model download/init are treated as OCR failures even if `ocrmypdf` exits successfully, so the app can retry on CPU or mark the job failed instead of accepting a non-searchable output.

## OCR Modes

- `Smart OCR (Skip text)`
  - Uses OCRmyPDF skip-text behavior for searchable pages.
- `Force OCR (All pages)`
  - Runs OCR on all pages.
  - Shows a confirmation warning because this mode can substantially increase output size and processing time.

## GPU OCR and Output Size Profiles

- `Enable GPU Acceleration (NVIDIA CUDA)`
  - Uses `ocrmypdf-easyocr` plugin when available in the current venv.
  - Worker automatically uses `--pdf-renderer sandwich` for EasyOCR compatibility.
  - On GPU/plugin-specific failures, worker retries once on CPU automatically.
  - Worker avoids duplicate EasyOCR plugin registration conflicts.
  - App launch automatically falls back to the venv `certifi` CA bundle when the host Python SSL trust path is broken, so first-run EasyOCR model downloads keep working.
- `Optimize for Smaller Output`
  - Applies balanced compression profile (`-O 2`, tuned JPEG/PNG quality).
  - Useful for sharing/email/cloud storage.
  - May reduce visual fidelity on faint/small text.
- Advanced controls include hover tooltips describing recommended use cases and tradeoffs.

## Parallelization and Priority

- Parallel-file presets: `Auto`, `Low`, `Balanced`, `High`, `Turbo`, `Max`, `Custom`.
- Custom worker count allowed up to configured max.
- Priority modes adjust process scheduling:
  - `Normal`
  - `Low`
  - `Background` (plus Linux `ionice` attempt)

## /mnt Fallback Strategy

When OCR fails due to mount/permission issues on `/mnt/...`:

1. File is copied to task temp staging.
2. OCR runs in temp location.
3. Result is atomically installed into the validated output folder.
4. Fallback usage is logged and surfaced in task status.

## Progress and Status UX

- Main window uses a custom dashboard shell with:
  - header action buttons for `Start OCR` and `Exit`
  - header menu buttons for `Tools` and `Help`
  - left sidebar cards for input source, advanced settings, and runtime stats
  - right-side queue and live-log cards
- Per-file progress bars with color coding:
  - `0-25`: red
  - `26-50`: orange
  - `51-75`: yellow
  - `76-99`: blue
  - `100`: green
- Batch progress bar uses matching color logic.
- Near completion, running jobs show a finalizing label around 95%.
- Queue table columns resize against the live viewport width instead of a fixed layout budget.
- On narrower queue panes, row controls switch to more compact labels such as `Log` and `Open` to reduce horizontal scrolling.
- Queue header shows:
  - unfinished item count as `Active`
  - total queued history count as `Total`
- Status values include:
  - `Queued`
  - `Running`
  - `Done`
  - `Skipped (Already Searchable)`
  - `Failed`
  - `Canceled`
- Runtime stats card cluster includes:
  - CPU card with system usage and app CPU subtext
  - RAM card with app RSS and system RAM subtext
  - GPU and VRAM cards when `nvidia-smi` is available
  - worker count and health summary lines
- Main splitter and queue/log splitter are user-resizable with larger drag handles and min-width safeguards.

## Logging

- Live global log stream in-app.
- Row-aware filtering: selected file only.
- Severity filters: any, warnings, errors.
- OCRmyPDF progress-bar lines are throttled to coarse percentage buckets before logging, so the viewer is not flooded with repeated sub-percent updates.
- Per-file log files stored under `logs/<batch>/`.
- Per-file dialog viewer via `View Log` button.
- Log summary includes timing, size ratios, memory, and CPU deltas.
- Job summary also records whether GPU->CPU retry fallback was used.

## File and Folder Actions

- Per-row action button:
  - `Cancel` while active
  - `Open Folder` when done/skipped/canceled
- Row context menu supports:
  - Copy input path
  - Copy output path
  - Copy log path
  - Open output folder
  - View log

## Session Restore and Exit Handling

- Queue state is persisted periodically to the app config location.
- On next launch, restore prompts validate queued file paths before re-adding them.
- Exiting while jobs are running prompts for one of three actions:
  - `Save Queue and Exit`
  - `Discard Queue and Exit`
  - `Cancel`
- `Save Queue and Exit` cancels running worker processes and restores unfinished files as queued items on the next launch.

## File Manager Integration

- File manager selection under `Tools -> File Manager`.
- Dynamic options per OS; unavailable managers are disabled.
- `Auto` picks first available configured manager.
- `System Default` uses platform opener fallback.
- `Custom Command`:
  - Requires `{path}` placeholder.
  - Validates executable presence.
  - Blocks shell-control characters and shell launcher wrappers.
  - Prompts once per session before first execution.

## CI Security Checks

- Secret scan with Gitleaks on push/PR.
- Dependency vulnerability scan with `pip-audit` on push/PR.

## Themes

- Theme modes:
  - `System` (default)
  - `Dark`
  - `Light`
- Theme selection is under `Tools -> Themes`.
- `Tools -> Reset to Defaults` restores theme and processing preferences.
- Drop zone includes visible bordered state and hover feedback.
- App/window icon loads from `assets/ocrestra.png` or `assets/ocrestra.ico` when present.

## Persistence

- Last directory remembered for dialogs.
- Last folder scan mode preference remembered for `Add Folder`.
- Queue state saved and restorable across restarts.
- Restore path list is size-limited and validated for safety.
