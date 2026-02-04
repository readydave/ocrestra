# Garuda Linux Desktop Launcher

This guide installs a Start Menu launcher for OCRestra on Garuda Linux (KDE Plasma).

## Prerequisites

- Repo is cloned locally (example: `~/scripts/OCR_App`)
- App launches correctly from terminal (`./setup_env.sh --run`)

## Install Launcher

From the repo root:

```bash
./scripts/install_linux_desktop_entry.sh
```

The script creates:

- `~/.local/share/applications/ocrestra.desktop`

It points to:

- `Exec=<repo>/setup_env.sh --run`
- `Path=<repo>`
- `Icon=<repo>/assets/ocrestra.png` (falls back to `application-pdf` if missing)

## Refresh Application Menu (Garuda KDE)

Usually this is automatic. If OCRestra does not appear immediately:

```bash
kbuildsycoca6 --noincremental
```

Then log out/in or restart Plasma shell.

## Updating After Code Changes

Most code changes do not require reinstalling the launcher.

Re-run install only if you:

- moved the repo to a different path
- changed launcher metadata (name/icon/categories)
- changed startup command

## Uninstall Launcher

```bash
rm -f ~/.local/share/applications/ocrestra.desktop
kbuildsycoca6 --noincremental
```
