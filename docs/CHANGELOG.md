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

### Changed

- App naming standardized to `OCRestra`.
- Runtime hardening for file handling and queue ingestion:
  - max queue/discovery/depth/input-size limits
  - safer temp cleanup boundaries
  - stricter output path handling (symlink protections)
  - safer worker config/path validation
