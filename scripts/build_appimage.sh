#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="OCRestra"
ARCH="x86_64"
BUILD_ROOT="$APP_DIR/build/appimage"
DIST_ROOT="$APP_DIR/dist"
APPDIR="$BUILD_ROOT/AppDir"
APPIMAGE_DEFAULT="$DIST_ROOT/${APP_NAME}-${ARCH}.AppImage"
APPIMAGE_OUTPUT="$APPIMAGE_DEFAULT"
ENSURE_ENV=1
KEEP_BUILD=0
ALLOW_DOWNLOAD=1

usage() {
  cat <<'EOF'
Usage:
  scripts/build_appimage.sh [options]

Options:
  --output <path>         Output AppImage path (default: dist/OCRestra-x86_64.AppImage)
  --skip-ensure           Skip running setup_env.sh --ensure
  --keep-build            Keep temporary AppDir/build artifacts
  --no-download-tool      Fail if appimagetool is not already available
  -h, --help              Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      [[ $# -ge 2 ]] || { echo "Error: --output requires a value." >&2; exit 1; }
      APPIMAGE_OUTPUT="$2"
      shift 2
      ;;
    --skip-ensure)
      ENSURE_ENV=0
      shift
      ;;
    --keep-build)
      KEEP_BUILD=1
      shift
      ;;
    --no-download-tool)
      ALLOW_DOWNLOAD=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option '$1'." >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Error: AppImage builds are only supported on Linux." >&2
  exit 1
fi

if [[ "$(uname -m)" != "$ARCH" ]]; then
  echo "Error: this script currently supports only $ARCH hosts." >&2
  exit 1
fi

if [[ -n "${LD_LIBRARY_PATH:-}" ]]; then
  echo "Info: unsetting LD_LIBRARY_PATH for a cleaner build environment."
  unset LD_LIBRARY_PATH
fi

if [[ -n "${SSL_CERT_FILE:-}" || -n "${CURL_CA_BUNDLE:-}" || -n "${REQUESTS_CA_BUNDLE:-}" ]]; then
  echo "Info: unsetting SSL_CERT_FILE/CURL_CA_BUNDLE/REQUESTS_CA_BUNDLE for downloader compatibility."
  unset SSL_CERT_FILE CURL_CA_BUNDLE REQUESTS_CA_BUNDLE
fi

if [[ -n "${CONDA_PREFIX:-}" || -n "${CONDA_DEFAULT_ENV:-}" ]]; then
  echo "Info: detected active Conda environment; unsetting Conda-specific variables for build isolation."
fi
unset CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL CONDA_EXE CONDA_PYTHON_EXE _CE_M _CE_CONDA
unset PYTHONHOME PYTHONPATH

if [[ "$ENSURE_ENV" -eq 1 ]]; then
  echo "Ensuring virtual environment dependencies..."
  /usr/bin/bash "$APP_DIR/setup_env.sh" --ensure
fi

VENV_PY="$APP_DIR/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Error: missing virtualenv Python at $VENV_PY" >&2
  exit 1
fi

VENV_BASE_PREFIX="$("$VENV_PY" - <<'PY'
import sys
print(sys.base_prefix)
PY
)"
shopt -s nocasematch
if [[ "$VENV_BASE_PREFIX" == *conda* || "$VENV_BASE_PREFIX" == *anaconda* || "$VENV_BASE_PREFIX" == *miniconda* || "$VENV_BASE_PREFIX" == *mambaforge* || "$VENV_BASE_PREFIX" == *micromamba* ]]; then
  cat <<EOF
Error: .venv is based on Conda Python: $VENV_BASE_PREFIX
For reliable AppImage builds, recreate .venv using system CPython (non-Conda), then retry:

  rm -rf "$APP_DIR/.venv"
  env -u CONDA_PREFIX -u CONDA_DEFAULT_ENV -u CONDA_SHLVL -u PYTHONHOME -u PYTHONPATH /usr/bin/bash "$APP_DIR/setup_env.sh" --ensure
  ./scripts/build_appimage.sh --skip-ensure
EOF
  exit 1
fi
shopt -u nocasematch

echo "Installing build dependencies (PyInstaller)..."
"$VENV_PY" -m pip install --upgrade pyinstaller

mkdir -p "$BUILD_ROOT" "$DIST_ROOT"

APPIMAGETOOL_BIN="$(command -v appimagetool || true)"
if [[ -z "$APPIMAGETOOL_BIN" ]]; then
  APPIMAGETOOL_BIN="$BUILD_ROOT/appimagetool-${ARCH}.AppImage"
  if [[ ! -x "$APPIMAGETOOL_BIN" ]]; then
    if [[ "$ALLOW_DOWNLOAD" -ne 1 ]]; then
      echo "Error: appimagetool not found and downloading is disabled." >&2
      exit 1
    fi
    echo "Downloading appimagetool..."
    TOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    downloaded=0
    if command -v curl >/dev/null 2>&1; then
      if curl -fsSL "$TOOL_URL" -o "$APPIMAGETOOL_BIN"; then
        downloaded=1
      else
        echo "Warning: curl download failed. Trying wget..."
      fi
    fi
    if [[ "$downloaded" -ne 1 ]] && command -v wget >/dev/null 2>&1; then
      if wget -qO "$APPIMAGETOOL_BIN" "$TOOL_URL"; then
        downloaded=1
      fi
    fi
    if [[ "$downloaded" -ne 1 ]]; then
      echo "Error: failed to download appimagetool." >&2
      echo "Tip: install appimagetool manually, or rerun after fixing TLS/certificate env settings." >&2
      exit 1
    fi
    chmod +x "$APPIMAGETOOL_BIN"
  fi
fi

echo "Building executable bundle with PyInstaller..."
PYI_ARGS=(
  -m PyInstaller
  --noconfirm
  --clean
  --name "$APP_NAME"
  --windowed
  --icon "$APP_DIR/assets/ocrestra.png"
  --collect-all PySide6
  --collect-submodules ocrmypdf
  --collect-data ocrmypdf
  --collect-submodules ocr_app
  --collect-data ocr_app
  --add-data "$APP_DIR/assets:assets"
  "$APP_DIR/ocr_gui.py"
)

if "$VENV_PY" - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("ocrmypdf_easyocr") else 1)
PY
then
  PYI_ARGS+=(--hidden-import ocrmypdf_easyocr --collect-submodules ocrmypdf_easyocr)
fi

"$VENV_PY" "${PYI_ARGS[@]}"

PYI_DIST="$APP_DIR/dist/$APP_NAME"
if [[ ! -d "$PYI_DIST" ]]; then
  echo "Error: expected PyInstaller output folder not found: $PYI_DIST" >&2
  exit 1
fi

rm -rf "$APPDIR"
mkdir -p \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -a "$PYI_DIST/." "$APPDIR/usr/bin/"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(dirname -- "$(readlink -f -- "$0")")"
export PATH="$HERE/usr/bin:$PATH"
exec "$HERE/usr/bin/OCRestra" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/ocrestra.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=OCRestra
Comment=Cross-platform batch OCR desktop app built with PySide6
Exec=OCRestra
Icon=ocrestra
Categories=Utility;Office;
Terminal=false
EOF

cp "$APPDIR/ocrestra.desktop" "$APPDIR/usr/share/applications/ocrestra.desktop"
cp "$APP_DIR/assets/ocrestra.png" "$APPDIR/ocrestra.png"
cp "$APP_DIR/assets/ocrestra.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/ocrestra.png"

mkdir -p "$(dirname -- "$APPIMAGE_OUTPUT")"
rm -f "$APPIMAGE_OUTPUT"

echo "Packaging AppImage..."
if [[ "$APPIMAGETOOL_BIN" == *.AppImage ]]; then
  APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL_BIN" "$APPDIR" "$APPIMAGE_OUTPUT"
else
  "$APPIMAGETOOL_BIN" "$APPDIR" "$APPIMAGE_OUTPUT"
fi

chmod +x "$APPIMAGE_OUTPUT"

if [[ "$KEEP_BUILD" -ne 1 ]]; then
  rm -rf "$APPDIR"
fi

cat <<EOF
Done.
AppImage: $APPIMAGE_OUTPUT

Runtime notes:
- Host system still needs: tesseract, ghostscript (gs), qpdf
- GPU mode also needs NVIDIA driver/CUDA runtime and working nvidia-smi
EOF
