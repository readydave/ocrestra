param(
    [ValidateSet("--ensure", "--run", "--alias")]
    [string]$Mode = "--ensure"
)

$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $AppDir ".venv"
$ReqFile = Join-Path $AppDir "requirements.txt"

function Get-PythonLauncher {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in @("3.13", "3.12", "3.11", "3.10")) {
            try {
                & py "-$ver" -c "import sys; print(sys.version)" | Out-Null
                return @("py", "-$ver")
            } catch {
            }
        }
        try {
            $sysVer = (& py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
            if ($sysVer -ne "3.14") {
                return @("py", "-3")
            }
        } catch {
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $sysVer = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
        if ($sysVer -ne "3.14") {
            return @("python")
        }
    }
    throw "No compatible Python interpreter found. Install Python 3.13 (recommended) or 3.12."
}

function Ensure-Env {
    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (Test-Path $venvPython) {
        $venvVer = (& $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
        if ($venvVer -eq "3.14") {
            Write-Host "Existing .venv uses Python 3.14; rebuilding with a compatible interpreter."
            Remove-Item -Recurse -Force $VenvDir
        }
    }

    if (-not (Test-Path $venvPython)) {
        $launcher = Get-PythonLauncher
        Write-Host "Creating virtual environment..."
        if ($launcher.Count -eq 1) {
            & $launcher[0] -m venv $VenvDir
        } else {
            & $launcher[0] $launcher[1] -m venv $VenvDir
        }
    }

    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Failed to create virtual environment at $VenvDir"
    }

    & $venvPython -m pip install --upgrade pip setuptools wheel
    if (Test-Path $ReqFile) {
        & $venvPython -m pip install --upgrade -r $ReqFile
    } else {
        & $venvPython -m pip install --upgrade PySide6 ocrmypdf psutil
    }
}

function Set-QtRuntime {
    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    $pluginRoot = (& $venvPython -c "from PySide6.QtCore import QLibraryInfo; print(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))").Trim()
    if ($pluginRoot -and (Test-Path $pluginRoot)) {
        $env:QT_PLUGIN_PATH = $pluginRoot
        $platformPath = Join-Path $pluginRoot "platforms"
        if (Test-Path $platformPath) {
            $env:QT_QPA_PLATFORM_PLUGIN_PATH = $platformPath
        }
    }
    if (-not $env:QT_QPA_PLATFORM) {
        $env:QT_QPA_PLATFORM = "windows"
    }
}

switch ($Mode) {
    "--ensure" {
        Ensure-Env
        Write-Host "Environment ready."
        Write-Host "Launch with: .\setup_env.ps1 --run"
    }
    "--run" {
        Ensure-Env
        Set-QtRuntime
        $venvPython = Join-Path $VenvDir "Scripts\python.exe"
        Push-Location $AppDir
        try {
            & $venvPython -m ocr_app
        } finally {
            Pop-Location
        }
    }
    "--alias" {
        Write-Host 'Set-Alias ocr-gui "$PWD\setup_env.ps1"'
        Write-Host 'Use: .\setup_env.ps1 --run'
    }
}
