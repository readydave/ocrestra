#!/usr/bin/env fish

set -g APP_DIR (cd (dirname (status --current-filename)); pwd)
set -g VENV_DIR "$APP_DIR/.venv"
set -g REQ_FILE "$APP_DIR/requirements.txt"

function pick_python
    for py in python3.13 python3.12 python3.11 python3.10
        if command -q $py
            echo $py
            return 0
        end
    end

    if command -q python3
        set -l sys_ver (python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if test "$sys_ver" != "3.14"
            echo python3
            return 0
        end
    end

    return 1
end

function ensure_env
    set -l venv_python "$VENV_DIR/bin/python"

    if test -x "$VENV_DIR/bin/python"
        set -l venv_ver ("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if test "$venv_ver" = "3.14"
            echo "Existing .venv uses Python 3.14; rebuilding with a compatible interpreter."
            rm -rf "$VENV_DIR"
        end
    end

    if not test -x "$VENV_DIR/bin/python"
        set -l py (pick_python)
        if test -z "$py"
            echo "Error: no compatible Python found."
            echo "Install python3.13 (recommended) or python3.12, then rerun."
            return 1
        end

        echo "Creating virtual environment with $py ..."
        $py -m venv "$VENV_DIR"
        or begin
            echo "Error: failed to create venv at $VENV_DIR"
            return 1
        end
    end

    if not test -x "$venv_python"
        echo "Error: missing venv Python at $venv_python"
        return 1
    end

    "$venv_python" -m pip install --upgrade pip setuptools wheel
    if test -f "$REQ_FILE"
        "$venv_python" -m pip install --upgrade -r "$REQ_FILE"
    else
        "$venv_python" -m pip install --upgrade PySide6 ocrmypdf psutil
    end
end

function configure_qt_runtime
    set -l plugin_root ("$VENV_DIR/bin/python" -c 'from PySide6.QtCore import QLibraryInfo; print(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))')

    if test -n "$plugin_root" -a -d "$plugin_root"
        set -gx QT_PLUGIN_PATH "$plugin_root"
        if test -d "$plugin_root/platforms"
            set -gx QT_QPA_PLATFORM_PLUGIN_PATH "$plugin_root/platforms"
        end
    end

    if not set -q QT_QPA_PLATFORM
        if set -q WAYLAND_DISPLAY
            set -gx QT_QPA_PLATFORM wayland
        else if set -q DISPLAY
            set -gx QT_QPA_PLATFORM xcb
        end
    end
end

set -l mode "--ensure"
if test (count $argv) -gt 0
    set mode $argv[1]
end

switch $mode
    case "--ensure"
        ensure_env; or exit 1
        echo "Environment ready."
        echo "Launch with: $APP_DIR/setup_env.fish --run"
    case "--run"
        ensure_env; or exit 1
        configure_qt_runtime
        cd "$APP_DIR"; or exit 1
        exec "$VENV_DIR/bin/python" -m ocr_app
    case "--alias"
        echo "alias ocr-gui '$APP_DIR/setup_env.fish --run'"
    case '*'
        echo "Usage:"
        echo "  setup_env.fish --ensure   # create/update .venv and install deps"
        echo "  setup_env.fish --run      # activate .venv and launch the GUI"
        echo "  setup_env.fish --alias    # print fish alias helper"
        exit 1
end
