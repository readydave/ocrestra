# OCRestra (PySide6 + OCRmyPDF)

Batch OCR desktop app for Linux/Windows with drag-drop queueing, process-level cancel, live metrics, log filtering, and persistent session restore.

## Documentation

- Docs index: `docs/README.md`
- User guide: `docs/USER_GUIDE.md`
- Feature reference: `docs/FEATURES.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Architecture: `docs/ARCHITECTURE.md`
- Code map: `docs/CODE_MAP.md`
- Developer guide: `docs/DEVELOPER.md`
- Function index: `docs/FUNCTION_INDEX.md`
- Function descriptions: `docs/FUNCTION_DESCRIPTIONS.md`
- Changelog: `docs/CHANGELOG.md`

## Highlights

- Drag/drop PDFs or folders (recursive scan)
- OCR modes:
  - `Smart OCR (Skip text)`
  - `Force OCR (All pages)`
- Parallel presets (`Auto`, `Low`, `Balanced`, `High`, `Turbo`, `Max`, `Custom`)
- Priority control (`Normal`, `Low Impact`, `Background`)
- Per-file progress with color bands + batch progress bar with same color logic
- Status differentiation (`Done`, `Skipped (Already Searchable)`, `Failed`, `Canceled`)
- Per-row actions:
  - `Cancel` while running
  - `Open Folder` when done/skipped
  - `View Log` in-app
- Log panel filters:
  - `All logs` / `Selected file only`
  - `Any level` / `Warnings only` / `Errors only`
- Context menu on row:
  - Copy input/output/log paths
  - Open folder
  - View log
- File-manager selection menu (`Tools -> File Manager`) with unavailable managers disabled
- `/mnt` permission/mount fallback via temp staging and move-back
- Queue/session persistence with restore prompt on restart
- Theme menu: `System` (default), `Dark`, `Light`

## Quick Start

### Linux (Bash/Zsh)

```bash
./setup_env.sh --run
```

### Linux (Fish)

```fish
./setup_env.fish --run
```

### Windows 11 (PowerShell)

```powershell
.\setup_env.ps1 --run
```

### Windows 11 (cmd.exe)

```bat
setup_env.bat --run
```

## Launching After First Setup

Fast direct launch from venv:

- Linux/macOS:
  - `./.venv/bin/python -m ocr_app`
- Windows:
  - `.\.venv\Scripts\python.exe -m ocr_app`

## Python Version Policy

Launch scripts prefer Python `3.13` / `3.12` / `3.11` / `3.10` and avoid `3.14` when auto-selecting interpreter for `.venv`.

## Required System OCR Tools

`ocrmypdf` requires these external binaries in `PATH`:

- Tesseract OCR
- Ghostscript
- qpdf

### Arch / Garuda

```bash
sudo pacman -S --needed tesseract tesseract-data-eng ghostscript qpdf
```

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-eng ghostscript qpdf
```

### Fedora

```bash
sudo dnf install -y tesseract tesseract-langpack-eng ghostscript qpdf
```

### Windows 11 (Winget example)

```powershell
winget install UB-Mannheim.TesseractOCR
winget install ArtifexSoftware.Ghostscript
winget install QPDF.QPDF
```

## Output, Logs, and State

- OCR output files are written to `OCR_Output` next to source PDFs.
- Output filename uses original basename (no `_ocr` suffix). If collision occurs: `_2`, `_3`, etc.
- Per-file logs are stored under `logs/<batch_id>/`.
- `Tools -> Open Log Folder` opens the current batch log folder.
- Queue state is saved under app config and restored on next launch (prompted).

## UI Notes

- `Path` selector controls how input paths display in table (`Full`, `Elided`, `Filename only`).
- Hovering files over drop zone triggers highlighted border feedback.
- Progress colors:
  - `0-25`: red
  - `26-50`: orange
  - `51-75`: yellow
  - `76-99`: blue
  - `100`: green

## File Manager Selection

Use `Tools -> File Manager`:

- `Auto (Recommended)` picks an installed manager for your OS.
- `System Default` uses Qt/system default open behavior.
- Specific managers are shown dynamically per platform and disabled when not installed.
- `Custom Command` supports `{path}` placeholder and validates executable/arguments.
- Shell launcher templates (`sh`, `bash`, `cmd`, `powershell`, etc.) are blocked for safety.
- Custom command execution prompts once per app session.

Example custom command:

```text
dolphin {path}
```

## Optional Linux Desktop Launcher

```bash
./scripts/install_linux_desktop_entry.sh
```

This generates `~/.local/share/applications/ocrestra.desktop` with your local install path.

## Development / CI

- Python dependencies are pinned in `requirements.txt` for reproducible installs.
- GitHub Actions workflow: `.github/workflows/ci.yml`
- Security workflow: `.github/workflows/security.yml` (Gitleaks + pip-audit)

## Security Hardening

- Queue/file safety limits:
  - max queued items: `5000`
  - max discovered PDFs per add operation: `20000`
  - max input file size: `2 GiB`
  - max recursive scan depth: `24`
- Path safety:
  - output temp cleanup restricted to configured temp root
  - output naming refuses symlink output directories/files
- Secret and dependency scanning:
  - CI: `.github/workflows/security.yml`
  - Local helper: `./scripts/security_scan.sh`
