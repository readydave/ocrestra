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
