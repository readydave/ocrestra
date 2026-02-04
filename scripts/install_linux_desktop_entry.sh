#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
TARGET_FILE="$TARGET_DIR/ocrestra.desktop"

mkdir -p "$TARGET_DIR"

cat >"$TARGET_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=OCRestra
Comment=OCRestra PySide6 batch OCR launcher with isolated virtualenv
Exec=$APP_DIR/setup_env.sh --run
Path=$APP_DIR
Terminal=false
Categories=Utility;
Icon=application-pdf
EOF

chmod 0644 "$TARGET_FILE"
echo "Installed desktop entry at: $TARGET_FILE"
