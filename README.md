# ModeShift v0.6.0 — Development build

Local-first Windows workload manager.

## New in this development build
- Top-right update notification checks the official latest published release on launch; user approval required for download and restart.
- Installer-aware update path distinguishes standard installations from standalone/portable EXEs.
- Five selectable visual themes, persisted locally in `%LOCALAPPDATA%\ModeShift`.
- Read-only dashboard Smart Scan with per-recommendation approval and snapshot-backed application of selected settings.

**Not yet tested on a physical Windows computer.** These are initial versions of the features, not a complete redesigned premium UI nor a comprehensive optimizer scanner. The official GitHub Releases update feed will remain unavailable until a versioned release is published. Keep a copy of your current working installer before testing.

## Build and installation
Run `UPLOAD_TO_GITHUB.bat` once to push this development release to your repository, then use GitHub Actions → newest successful run → `ModeShift-INSTALLER` artifact to download `ModeShiftSetup.exe`. Do not publish until the installer and updater are verified on Windows.

Running from source requires Python and dependencies from `requirements-runtime.txt`.
