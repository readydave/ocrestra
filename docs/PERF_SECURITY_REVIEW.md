# Performance & Security Refactor Opportunities

## Scope
Quick static review of the OCR worker/runtime paths with emphasis on command execution, filesystem safety, and periodic metrics collection.

## High-value opportunities

1. **Avoid buffering full OCRmyPDF stdout/stderr in memory** (Performance + reliability)
   - Current worker execution uses `subprocess.run(..., stdout=PIPE, stderr=PIPE, text=True)`, which captures full output in-memory before returning.
   - For noisy failures or verbose plugin output, this can inflate memory and delay error propagation.
   - Refactor direction:
     - Stream output incrementally to the task log file (and optionally a bounded in-memory ring buffer for UI summaries).
     - Preserve only the final N KB for user-facing error messages.

2. **Cache plugin entry-point discovery** (Performance)
   - `_easyocr_plugin_autoregistered()` scans package entry points each OCR run.
   - Entry-point enumeration can be relatively expensive and is invariant for process lifetime.
   - Refactor direction:
     - Memoize the result (e.g., `functools.lru_cache(maxsize=1)`) and reuse for all jobs in the process.

3. **Throttle GPU metrics polling or move it off the UI-thread timer path** (Performance)
   - UI polls metrics every second and calls `nvidia-smi` via subprocess.
   - Repeated process spawning can cause noticeable overhead, especially on slower systems.
   - Refactor direction:
     - Poll GPU metrics less frequently (e.g., every 3–5s), or cache previous values and update asynchronously.
     - Consider running GPU probes in a lightweight background worker to avoid UI jitter.

4. **Harden output path handling against symlink/race edge cases** (Security)
   - `_safe_output_pdf()` validates extension and some symlink conditions, but protection can be bypassed by post-check path swaps (TOCTOU) in hostile multi-user contexts.
   - Refactor direction:
     - Resolve and validate full destination ancestry using strict checks.
     - For final write, use lower-level open flags where available (`O_NOFOLLOW`) and atomic replacement into trusted directories.

5. **Strengthen queue-state file trust model** (Security)
   - State file safety checks include symlink and world/group writability checks, but parent directory ownership/permissions are not validated.
   - In shared environments, weak directory permissions could still enable tampering.
   - Refactor direction:
     - Validate parent directory ownership and mode on POSIX.
     - Optionally store state under an application-private subdirectory with enforced `0700` permissions.

6. **Reduce path-resolution overhead during large folder scans** (Performance)
   - Recursive discovery resolves every candidate with `.resolve()` while walking potentially large trees.
   - This is robust but can be expensive across network mounts or deep trees.
   - Refactor direction:
     - Delay `resolve()` until dedupe-confirmation requires canonicalization, or use `(st_dev, st_ino)` dedupe from `stat()` for local filesystems.
     - Keep current depth and count limits (already good defensive controls).

## Suggested implementation order
1. Stream subprocess output + bounded error capture.
2. Cache plugin discovery.
3. Throttle/asynchronize GPU metrics polling.
4. Harden output/state filesystem trust checks.
5. Optimize discovery canonicalization path for very large scans.
