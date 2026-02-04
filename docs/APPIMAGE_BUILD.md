# Build AppImage (Linux)

This project includes a helper script to build an AppImage from the current source tree.

## What the AppImage includes

- OCRestra executable bundle (PyInstaller)
- Python runtime and Python package dependencies from `.venv`
- App icon and desktop metadata

## What the AppImage does not fully replace

The target Linux machine still needs OCR system tools installed:

- `tesseract`
- `ghostscript` (`gs`)
- `qpdf`

For GPU mode, target machine also needs:

- NVIDIA driver/CUDA runtime compatible with installed `torch`
- working `nvidia-smi`

## Build Requirements

- Linux `x86_64`
- Project checked out locally
- Internet access (first build only) to fetch `appimagetool` if not already installed
- `curl` or `wget` (for downloading `appimagetool` automatically)
- Non-Conda CPython venv recommended for packaging reliability

## Build Command

From repo root:

```bash
./scripts/build_appimage.sh
```

Default output:

```text
dist/OCRestra-x86_64.AppImage
```

## Useful Options

```bash
# Custom output path
./scripts/build_appimage.sh --output /tmp/OCRestra.AppImage

# Skip venv dependency ensure step
./scripts/build_appimage.sh --skip-ensure

# Keep temporary AppDir/build artifacts
./scripts/build_appimage.sh --keep-build

# Require preinstalled appimagetool (do not auto-download)
./scripts/build_appimage.sh --no-download-tool
```

## Common Download Issue (TLS/Certificate env)

If you use Conda or custom SSL environment variables, downloading `appimagetool` may fail with cert-path errors.

The build script now clears these variables automatically:

- `SSL_CERT_FILE`
- `CURL_CA_BUNDLE`
- `REQUESTS_CA_BUNDLE`

If you still hit download failures, install `appimagetool` manually and rerun with:

```bash
./scripts/build_appimage.sh --no-download-tool
```

## Conda-Based venv Issue

If your `.venv` was created from Conda Python, PyInstaller may fail with Qt/OpenSSL/binary mismatch errors.

Use a non-Conda Python-backed venv for AppImage builds:

```bash
rm -rf .venv
env -u CONDA_PREFIX -u CONDA_DEFAULT_ENV -u CONDA_SHLVL -u PYTHONHOME -u PYTHONPATH /usr/bin/bash ./setup_env.sh --ensure
./scripts/build_appimage.sh --skip-ensure
```

## Running the Result

```bash
chmod +x dist/OCRestra-x86_64.AppImage
./dist/OCRestra-x86_64.AppImage
```

## Distribution Recommendation

- Do **not** commit AppImage binaries to git history.
- Upload AppImage files as GitHub Release assets.
