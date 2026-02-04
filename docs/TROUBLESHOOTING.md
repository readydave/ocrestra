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

## OCR Works but "Too few characters" Appears

This can be normal for low-text or decorative pages.  
If final output is produced and searchable, no action is required.

## Output Missing on `/mnt`

If direct output fails, OCRestra retries via temp staging.  
Check per-file log for fallback activity and final output path.

## Missing OCR Dependencies

If OCR does not start or fails early, verify:

- `tesseract`
- `gs` (Ghostscript)
- `qpdf`

See root `README.md` for install commands by distro.

## Push to GitHub Fails with "fetch first"

Remote has initial commit history not in local.

Typical resolution for fresh repos:

- `git fetch origin --prune`
- `git push --force-with-lease -u origin main`

## If You Need Deep Diagnostics

1. Open per-file log with `View Log`.
2. Use `Tools -> Open Log Folder`.
3. Include log excerpt, platform, Python version, and exact launch command in bug reports.
