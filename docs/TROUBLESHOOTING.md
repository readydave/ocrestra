# OCRestra Troubleshooting

## Qt Platform Plugin Errors

Example:

- `Could not find the Qt platform plugin "wayland" ...`
- `Could not find the Qt platform plugin "xcb" ...`

Actions:

1. Launch using setup scripts (`setup_env.sh --run` / `setup_env.fish --run`) so Qt plugin paths are set.
2. Ensure PySide6 is installed in `.venv`.
3. On Linux, confirm desktop session variables (`WAYLAND_DISPLAY` or `DISPLAY`) exist.

## `setup_env.fish: command not found`

Run it from the project directory and include `./`:

- `cd ~/scripts/OCR_App`
- `./setup_env.fish --run`

## Relative Import Error from `job_runner.py`

If you run `ocr_app/job_runner.py` directly, you may see:

- `ImportError: attempted relative import with no known parent package`

Use package entrypoint instead:

- `python -m ocr_app`

## `/bin/sh ... rl_print_keybinding` Warnings

This usually indicates a polluted `LD_LIBRARY_PATH` from another toolchain.

Try:

- `env -u LD_LIBRARY_PATH git <command>`
- `env -u LD_LIBRARY_PATH ./.venv/bin/python -m ocr_app`

## File Manager Opens/Closes Unexpectedly

1. In app, set `Tools -> File Manager -> Auto` or choose a known installed manager.
2. Avoid broken custom commands.
3. If needed, set `System Default`.

## Left Panel Text Is Clipped / Hard to Resize

1. Drag the main splitter handle between the left config pane and right queue pane.
2. Drag the queue/log splitter to rebalance center and bottom sections.
3. If layout still feels off, restart the app to reset splitter defaults.

## OCR Works but "Too few characters" Appears

This can be normal for low-text or decorative pages.  
If final output is produced and searchable, no action is required.

## GPU Mode Fails Immediately

If GPU mode is enabled and OCR fails before processing:

1. Confirm plugin is installed in the app venv:
   - `./.venv/bin/python -m pip show ocrmypdf-easyocr`
2. Confirm NVIDIA runtime is healthy:
   - `nvidia-smi`
3. If plugin is missing, install:
   - `./.venv/bin/python -m pip install ocrmypdf-easyocr`
4. Retry with GPU disabled to confirm CPU path works.

Note: OCRestra uses EasyOCR with `--pdf-renderer sandwich` for compatibility.

## Output PDF Is Much Larger Than Input

Example OCRmyPDF warning:

- `The output file size is 2.85× larger than the input file.`

Common causes:

- `--deskew` (or related transforms) triggers image transcoding.
- `jbig2` optimization tools are not installed.
- Force OCR on already-searchable PDFs increases file size.
- GPU EasyOCR with sandwich renderer can produce larger output.

Actions:

1. Use `Smart OCR (Skip text)` for mixed/searchable batches.
2. Install optional `jbig2` encoder package on your platform.
3. Enable `Optimize for Smaller Output` in `Advanced` for balanced compression.
4. Compare output quality/settings before forcing OCR on all pages.

## GPU/VRAM Metrics Show N/A

`Show Stats` includes GPU and VRAM only when `nvidia-smi` is available and functional.

If GPU metrics show `N/A`:

1. Run `nvidia-smi` in the same shell session.
2. If it fails, fix driver/runtime first.
3. Relaunch OCRestra after `nvidia-smi` is working.

## "Input exceeds limit" / oversized file skipped

OCRestra enforces a max input file size (`2 GiB` by default).  
Large files are skipped for stability and resource protection.

If needed, split the PDF before OCR or raise `MAX_INPUT_FILE_BYTES` in `ocr_app/config.py`.

## Output Missing on `/mnt`

If direct output fails, OCRestra retries via temp staging.  
Check per-file log for fallback activity and final output path.

## Missing OCR Dependencies

If OCR does not start or fails early, verify:

- `tesseract`
- `gs` (Ghostscript)
- `qpdf`

See root `README.md` for install commands by distro.

## Linux Portal Warning at Launch

Example:

- `qt.qpa.services: Failed to register with host portal ... App info not found ...`

Usually harmless in local/dev runs without an installed desktop entry.  
If desired, install the desktop entry script from root `README.md` to provide a matching app ID.

## If You Need Deep Diagnostics

1. Open per-file log with `View Log`.
2. Use `Tools -> Open Log Folder`.
3. Include log excerpt, platform, Python version, and exact launch command in bug reports.
