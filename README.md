# ModeShift v0.5.4 — Windows installer edition

A free Windows PC configuration app with local presets, hardware monitoring, resource guard and reversible changes. **Development build; not hardware validated or signed.**

## Installing without Python
Once the release pipeline is activated, download `ModeShiftSetup.exe` from the latest GitHub Release of `lolipopkins/ModeShift`. Install normally; it creates Start menu shortcuts and optionally a desktop icon. **There is no compiled installer inside this source ZIP**. GitHub Windows Actions produces the installer after the repository is created, files uploaded and the version tag pushed.

Existing developer builds can be replaced without deleting data: preferences and snapshots live in `%LOCALAPPDATA%\ModeShift`. Keep a backup before first upgrade. `INSTALLER_GUIDE.md` explains the installer and one-click updater workflow.

## Developer build
`build_exe.bat` still builds a portable EXE for development. The release workflow builds both the EXE and installer automatically on Windows. Source lives under `src/`; tests under `tests/`. No paid dependencies are required.

Read `GITHUB_SETUP.md` for publication and `UPDATE_GUIDE.md` for update-feed design. GPU monitoring, unattended guard and system changes require real Windows validation before describing this app as production-ready.
