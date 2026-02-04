# OCRestra Features

## Queue Ingestion

- Drag-and-drop accepts PDF files and folders.
- Folder import scans recursively for `.pdf` (case-insensitive).
- Symlink directory traversal is disabled during folder walk.
- Duplicate files are de-duplicated per queue by resolved path.
- Queue and discovery limits:
  - max queued files: `5000`
  - max discovered PDFs per add operation: `20000`
  - max scan depth: `24`
  - max accepted input file size: `2 GiB`

## OCR Execution Engine

- OCR processing uses OCRmyPDF library directly (no Docker shell pipeline).
- Each queued file runs in its own Python multiprocessing worker.
- UI remains non-blocking while jobs run.
- Cancel actions terminate worker processes immediately.

## OCR Modes

- `Smart OCR (Skip text)`
  - Uses OCRmyPDF skip-text behavior for searchable pages.
- `Force OCR (All pages)`
  - Runs OCR on all pages.

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
3. Result is moved back to output folder.
4. Fallback usage is logged and surfaced in task status.

## Progress and Status UX

- Per-file progress bars with color coding:
  - `0-25`: red
  - `26-50`: orange
  - `51-75`: yellow
  - `76-99`: blue
  - `100`: green
- Batch progress bar uses matching color logic.
- Near completion, running jobs show a finalizing label around 95%.
- Status values include:
  - `Queued`
  - `Running`
  - `Done`
  - `Skipped (Already Searchable)`
  - `Failed`
  - `Canceled`

## Logging

- Live global log stream in-app.
- Row-aware filtering: selected file only.
- Severity filters: any, warnings, errors.
- Per-file log files stored under `logs/<batch>/`.
- Per-file dialog viewer via `View Log` button.
- Log summary includes timing, size ratios, memory, and CPU deltas.

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
- Drop zone includes visible bordered state and hover feedback.

## Persistence

- Last directory remembered for dialogs.
- Queue state saved and restorable across restarts.
- Restore path list is size-limited and validated for safety.
