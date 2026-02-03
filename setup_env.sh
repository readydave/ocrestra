#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
REQ_FILE="$APP_DIR/requirements.txt"

pick_python() {
  local py
  for py in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$py" >/dev/null 2>&1; then
      echo "$py"
      return 0
    fi
  done

  if command -v python3 >/dev/null 2>&1; then
    local ver
    ver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [[ "$ver" != "3.14" ]]; then
      echo "python3"
      return 0
    fi
  fi
  return 1
}

ensure_env() {
  local venv_python="$VENV_DIR/bin/python"

  if [[ -x "$VENV_DIR/bin/python" ]]; then
    local venv_ver
    venv_ver="$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [[ "$venv_ver" == "3.14" ]]; then
      echo "Existing .venv uses Python 3.14; rebuilding with a compatible interpreter."
      rm -rf "$VENV_DIR"
    fi
  fi

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    local py
    if ! py="$(pick_python)"; then
      echo "Error: no compatible Python found."
      echo "Install Python 3.13 (recommended) or 3.12, then rerun."
      return 1
    fi
    echo "Creating virtual environment with $py ..."
    "$py" -m venv "$VENV_DIR"
  fi

  if [[ ! -x "$venv_python" ]]; then
    echo "Error: missing venv Python at $venv_python"
    return 1
  fi

  "$venv_python" -m pip install --upgrade pip setuptools wheel
  if [[ -f "$REQ_FILE" ]]; then
    "$venv_python" -m pip install --upgrade -r "$REQ_FILE"
  else
    "$venv_python" -m pip install --upgrade PySide6 ocrmypdf psutil
  fi
}

configure_qt_runtime() {
  local plugin_root
  plugin_root="$("$VENV_DIR/bin/python" -c 'from PySide6.QtCore import QLibraryInfo; print(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))' 2>/dev/null || true)"
  if [[ -n "$plugin_root" && -d "$plugin_root" ]]; then
    export QT_PLUGIN_PATH="$plugin_root"
    if [[ -d "$plugin_root/platforms" ]]; then
      export QT_QPA_PLATFORM_PLUGIN_PATH="$plugin_root/platforms"
    fi
  fi

  if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
    if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
      export QT_QPA_PLATFORM=wayland
    elif [[ -n "${DISPLAY:-}" ]]; then
      export QT_QPA_PLATFORM=xcb
    fi
  fi
}

mode="${1:---ensure}"
case "$mode" in
  --ensure)
    ensure_env
    echo "Environment ready."
    echo "Launch with: $APP_DIR/setup_env.sh --run"
    ;;
  --run)
    ensure_env
    configure_qt_runtime
    cd "$APP_DIR"
    exec "$VENV_DIR/bin/python" -m ocr_app
    ;;
  --alias)
    echo "alias ocr-gui='$APP_DIR/setup_env.sh --run'"
    ;;
  *)
    echo "Usage:"
    echo "  setup_env.sh --ensure   # create/update .venv and install deps"
    echo "  setup_env.sh --run      # activate .venv and launch GUI"
    echo "  setup_env.sh --alias    # print bash alias helper"
    exit 1
    ;;
esac
