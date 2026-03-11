# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Added `docs/IMPLEMENTATION_PLAN.md` to track staged performance and security refactors.
- Started formal release versioning with a repository `VERSION` file and package `__version__` export.
- Added targeted `unittest` coverage for output-path hardening, folder-scan dedupe/symlink handling, and secure state-directory checks.
- Added an exit prompt for running batches so unfinished files can be saved for restore on the next launch or discarded on exit.

### Changed
- Cached EasyOCR plugin auto-registration detection to avoid repeated entry-point scans per OCR job.
- Switched OCR command execution to streamed subprocess output with bounded tail capture for error reporting.
- Treat EasyOCR plugin tracebacks during model download/init as backend failures even when `ocrmypdf` exits `0`, so GPU jobs now retry on CPU or fail instead of silently producing non-searchable output.
- Added automatic `certifi` CA-bundle fallback in the app and launcher scripts when the host Python/OpenSSL trust path is broken, so EasyOCR model downloads do not depend on machine-specific SSL packaging.
- Reduced GPU metric probe overhead by caching `nvidia-smi` results between UI refresh cycles.
- Reset the queue table's horizontal scroll offset whenever responsive widths fit the viewport, preventing clipped-looking first-column cells in the redesigned dashboard.
- Throttled OCRmyPDF progress-bar log spam so repeated sub-percent updates no longer flood the live log viewer or per-file logs.
- Inset table row action buttons to avoid clipped rounded borders at the right edge, and added inline help for the `Path display` setting in Advanced Settings.
- Reserved enough queue-card/table height to keep at least one full queue row visible when the queue/log splitter is tight.
- Hardened queue-state persistence by enforcing private config directory permissions before load/save.
- Optimized large folder PDF discovery by avoiding eager path resolution, skipping symlinked inputs, and deduping by file identity when available.
- Hardened final output installation by staging PDFs in the temp workspace and atomically replacing the destination from a validated output directory.
- Made queue-table column sizing responsive to the actual viewport and compacted row action labels on narrow layouts to reduce horizontal scrolling.
- Reworked the main dashboard into a custom header/sidebar/card layout with header menu buttons, queue active/total badges, compact runtime stat cards, and a tighter live-log panel.
- Updated documentation indexes and planning docs to surface the performance/security review, active to-do list, and expected doc maintenance workflow.
- Recorded a clean local dependency and secret-scan baseline (`pip-audit`: no known vulnerabilities, `gitleaks`: no leaks found).

## [0.1.0] - 2026-03-11

### Added
- Initial public baseline for OCRestra app/docs structure and OCR workflow support.
