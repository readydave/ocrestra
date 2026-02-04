# OCRestra User Guide

## 1) What OCRestra Does

OCRestra is a PySide6 desktop app for batch OCR on PDF files using OCRmyPDF.  
It runs OCR jobs as worker processes so the UI stays responsive and jobs can be canceled.

## 2) Launching

- Linux bash/zsh: `./setup_env.sh --run`
- Linux fish: `./setup_env.fish --run`
- Windows PowerShell: `.\setup_env.ps1 --run`
- Windows cmd: `setup_env.bat --run`

Direct venv launch:

- Linux/macOS: `./.venv/bin/python -m ocr_app`
- Windows: `.\.venv\Scripts\python.exe -m ocr_app`

## 3) Basic Workflow

1. Add files via drag/drop or `Add PDFs` / `Add Folder`.
2. If using `Add Folder`, choose scan mode:
   - `Recursive (All subfolders)`
   - `Top-level only`
3. Open `Advanced` to choose OCR mode, path display, priority, and parallel count.
4. Click `Start OCR`.
5. Monitor per-file progress bars, batch progress, and logs.
6. Use row actions:
   - `Cancel` while running
   - `Open Folder` when done or skipped
   - `View Log` to inspect per-file log output

## 4) Controls Overview

- `Advanced` section
  - `OCR mode`: `Smart OCR (Skip text)` or `Force OCR (All pages)`
  - `Priority`: `Normal Priority`, `Low Impact`, `Background`
  - `Parallel files`: presets plus custom value
  - `Path display`: `Full path`, `Elided`, `Filename only`
- `Show Stats`
  - Toggles visibility of the CPU/RAM metrics row.

## 5) Menus

- `File`: add files/folders, start/cancel, exit.
- `Tools`
  - `Themes` (`System`, `Dark`, `Light`)
  - `Reset to Defaults`
  - `Open Log Folder`
  - `File Manager` selector (`Auto`, `System`, platform-specific options, `Custom Command`)
- `Help`
  - `Usage`
  - `About`

## 6) Logs and Metrics

- Live log panel supports:
  - Scope filter: `All logs` or `Selected file only`
  - Level filter: `Any`, `Warnings only`, `Errors only`
- Per-file logs are written to `logs/<batch_id>/`.
- Metrics row includes app CPU/RAM, system CPU/RAM, and active/queued count.

## 7) Output Behavior

- Output goes to `OCR_Output` under each input file's parent folder.
- File names keep original base name.
- If a name exists, numeric suffixes are applied (`_2`, `_3`, ...).

## 8) Cancel Behavior

- Cancel terminates the worker process and marks the row as `Canceled`.
- Temporary work directory for that task is cleaned up.

## 9) Session Restore

- Queue state is saved periodically.
- On next launch, OCRestra prompts to restore queued items.
- Restored paths are validated as existing `.pdf` files.

## 10) Requirements

OCRmyPDF requires system tools in `PATH`:

- Tesseract OCR
- Ghostscript
- qpdf

See root `README.md` for distro-specific install commands.

## 11) Operational Limits (Security/Stability)

OCRestra enforces the following defaults:

- Max queued files: `5000`
- Max discovered PDFs per add operation: `20000`
- Max recursive scan depth: `24`
- Max input PDF size: `2 GiB`

If a limit is hit, files are skipped and a warning is shown in the UI/log.
