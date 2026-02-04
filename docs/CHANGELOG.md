# Changelog

All notable changes to OCRestra should be documented here.

## [Unreleased]

### Added

- Documentation set under `docs/`:
  - user guide
  - feature reference
  - troubleshooting
  - architecture
  - developer guide
  - function index
- Security CI workflow:
  - Gitleaks secret scanning
  - pip-audit dependency scanning
- Local security helper script:
  - `scripts/security_scan.sh`
- Folder scan mode prompt when using `Add Folder`:
  - recursive (`All subfolders`)
  - non-recursive (`Top-level only`)
- `Tools -> Reset to Defaults` to restore UI/processing preferences.
- Advanced OCR controls:
  - NVIDIA GPU acceleration toggle (`ocrmypdf-easyocr`)
  - output-size optimization toggle (balanced compression)
  - inline hover help for GPU/compression use cases
- Footer runtime metrics for NVIDIA GPU utilization and VRAM (when `nvidia-smi` is available).

### Changed

- App naming standardized to `OCRestra`.
- UI refactor for cross-platform release:
  - dual-pane layout with splitter resizing
  - scrollable configuration pane
  - collapsible `Advanced` controls
  - queue empty-state overlay
  - metrics visibility toggle (`Show Stats`)
- Theme menu moved under `Tools -> Themes`.
- Theme engine updated with adaptive dark/light/system styling and clearer popup/dropdown contrast.
- Runtime hardening for file handling and queue ingestion:
  - max queue/discovery/depth/input-size limits
  - safer temp cleanup boundaries
  - stricter output path handling (symlink protections)
  - safer worker config/path validation
- Worker OCR command execution now:
  - validates `ocrmypdf` availability with `shutil.which`
  - supports EasyOCR plugin auto-registration behavior
  - forces `--pdf-renderer sandwich` when EasyOCR GPU mode is enabled
  - supports optional size-optimized output profile flags
- Splitter UX tuning:
  - larger draggable splitter handles
  - non-collapsible pane behavior
  - improved default splitter sizes and pane minimum widths
- Theme/QSS cleanup:
  - removed unsupported `content` property usage that caused terminal warnings
