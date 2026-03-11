# Implementation Plan: Performance + Security Fixes

This plan turns the findings in `docs/PERF_SECURITY_REVIEW.md` into staged, shippable changes.

## Phase 1 — Fast Wins (Low risk, high ROI)

### 1) Cache EasyOCR plugin discovery
- **Change**: Memoize `_easyocr_plugin_autoregistered()` for process lifetime.
- **Why**: Entry-point scans are repetitive and invariant in a running process.
- **Acceptance**:
  - Function behavior remains identical across first and subsequent invocations.
  - No user-facing change in GPU plugin behavior.

### 2) GPU metrics polling optimization
- **Change**:
  - Poll `nvidia-smi` less frequently (e.g., every 3–5 seconds), while UI labels still refresh every second from cached values.
  - Keep timeout and failure handling as-is.
- **Why**: Reduce subprocess spawn overhead and potential UI jitter.
- **Acceptance**:
  - UI remains responsive during active OCR workloads.
  - GPU metrics still update periodically and degrade gracefully when unavailable.

## Phase 2 — Subprocess Output Reliability

### 3) Stream OCRmyPDF output instead of full buffering
- **Change**:
  - Replace `subprocess.run(..., stdout=PIPE, stderr=PIPE)` with streaming via `Popen` and incremental read.
  - Forward output to per-task log in real time.
  - Keep a bounded tail buffer (e.g., last 8–32 KB) for concise error surfacing.
- **Why**: Avoid memory spikes and improve observability on long/noisy jobs.
- **Acceptance**:
  - No unbounded growth from command output capture.
  - Failure messages still include useful, recent OCR output context.

## Phase 3 — Filesystem Hardening

### 4) Harden output write path
- **Change**:
  - Strengthen destination checks (resolved ancestry, symlink refusal across key segments).
  - Prefer atomic write/replace patterns in trusted destination directories.
  - Where practical, use no-follow semantics for final file operations on POSIX.
- **Why**: Reduce symlink/TOCTOU risk in multi-user or adversarial local environments.
- **Acceptance**:
  - Legitimate writes still succeed.
  - Symlink-based path confusion attempts are rejected.

### 5) Harden queue-state storage trust model
- **Change**:
  - Ensure parent config directory is private (`0700`) on POSIX.
  - Validate ownership/permissions before load/save.
- **Why**: Prevent local tampering with persisted queue state.
- **Acceptance**:
  - Existing state restore works for normal users.
  - Unsafe directory/file permission scenarios are skipped with log notice.

## Phase 4 — Large-Tree Discovery Scalability

### 6) Optimize PDF discovery canonicalization
- **Change**:
  - Avoid eager `resolve()` for every candidate during deep scans.
  - Use lighter dedupe strategy first, with canonicalization only when necessary.
- **Why**: Improve throughput on large trees and network filesystems.
- **Acceptance**:
  - Discovery stays bounded by existing safety limits.
  - Measurable reduction in scan time on large folder benchmarks.

## Validation Strategy

For each phase:
1. Add/adjust targeted unit or integration tests where practical.
2. Run manual smoke test with:
   - CPU-only OCR
   - GPU-enabled OCR (when available)
   - folder scan with nested directories
3. Run security checks from `scripts/security_scan.sh`.
4. Capture before/after metrics for memory usage and scan latency.

## Rollout Notes

- Ship by phase to minimize regression blast radius.
- Keep changelog entries under `changelog.md` per release.
- Start semantic versioning at `0.1.0`; bump to `0.2.0` once core hardening/performance phases land.
