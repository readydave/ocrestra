# OCRestra Developer Guide

## Repository Layout

- `ocr_app/ui.py`: Main GUI logic and orchestration.
- `ocr_app/job_runner.py`: Worker process OCR execution.
- `ocr_app/models.py`: Data model(s).
- `ocr_app/config.py`: Constants and path settings.
- `ocr_app/themes.py`: Theme application helpers.
- `ocr_app/__main__.py`: Package entrypoint.
- `ocr_gui.py`: Script entrypoint wrapper.
- `setup_env.*`: Cross-platform bootstrap launch scripts.
- `.github/workflows/ci.yml`: Basic syntax checks.

## Local Dev Workflow

1. `./setup_env.sh --ensure` (or fish/PowerShell equivalent)
2. Launch with `python -m ocr_app`
3. Run compile checks:
   - `python -m py_compile ocr_gui.py ocr_app/__main__.py ocr_app/ui.py ocr_app/job_runner.py ocr_app/themes.py ocr_app/models.py ocr_app/config.py`
4. Run local security scan helper (optional but recommended):
   - `./scripts/security_scan.sh`

## Coding Notes

- Keep UI responsive; avoid long blocking calls in Qt main thread.
- Worker communication should happen through queue events only.
- New per-task data should generally live in `TaskItem.metrics`.
- For security-sensitive command execution, avoid `shell=True` and validate inputs.
- Keep safety limits centralized in `ocr_app/config.py` and avoid hardcoding thresholds in UI/worker code.

## Adding a New Feature

1. Add controls/widgets in `MainWindow._build_ui`.
2. Wire actions/signals in `_build_ui` or `_build_menus`.
3. Persist settings in `QSettings` on load/save.
4. Update docs:
   - `FEATURES.md`
   - `USER_GUIDE.md`
   - `README.md` highlights if user-facing.

## Function Reference

See `FUNCTION_INDEX.md` for an inventory of module functions and class methods.

Regenerate it with:

```bash
python scripts/gen_function_index.py
```

(If script is not present, regenerate manually from current source and update `docs/FUNCTION_INDEX.md`.)
