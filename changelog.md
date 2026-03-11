# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Added `docs/IMPLEMENTATION_PLAN.md` to track staged performance and security refactors.
- Started formal release versioning with a repository `VERSION` file and package `__version__` export.

### Changed
- Cached EasyOCR plugin auto-registration detection to avoid repeated entry-point scans per OCR job.
- Switched OCR command execution to streamed subprocess output with bounded tail capture for error reporting.
- Reduced GPU metric probe overhead by caching `nvidia-smi` results between UI refresh cycles.
- Hardened queue-state persistence by enforcing private config directory permissions before load/save.
- Optimized large folder PDF discovery by avoiding eager path resolution and skipping symlinked files.
- Tightened output-path validation by rejecting symlink segments in destination directory paths.

## [0.1.0] - 2026-03-11

### Added
- Initial public baseline for OCRestra app/docs structure and OCR workflow support.
