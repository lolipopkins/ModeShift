# ModeShift Windows installer (v0.5.4)

## For first-time users
Once a GitHub release is published, download `ModeShiftSetup.exe` from its release page. Run the installer normally; no Python, batch scripts or command prompt required. By default it installs for the current user in `%LOCALAPPDATA%\Programs\ModeShift`, creates a Start menu entry and optionally a desktop shortcut.

## Updates
ModeShift's Settings > Check for updates > Download and install fetches `ModeShift.exe` from `latest.json`, verifies SHA-256 and replaces the currently running EXE after it exits. Installed and portable editions share the same app binary, so the update mechanism works in both. The separate setup installer is primarily for first installation. Future installer releases can also be run over an existing installation and use the same Inno Setup AppId.

**Caveat:** An in-app binary replacement is not an Inno Setup transaction, so uninstall metadata might not reflect a later in-app updated EXE. Do not install ModeShift under Program Files (requires elevation for app updates). ModeShift is not code-signed yet; Windows SmartScreen may warn. SHA-256 verification does *not* prove publisher authenticity if a feed is compromised. The update feed must be controlled by the publisher and should eventually adopt release-signature verification.

## User data preservation
Preferences, presets, snapshots, measurements and guard logs live at `%LOCALAPPDATA%\ModeShift`, separate from `%LOCALAPPDATA%\Programs\ModeShift`. The installer and uninstaller do not remove that user-data folder. Before initial setup, back it up if you already used a development build.

## GitHub build
GitHub Actions (Windows runner) installs Python dependencies, runs tests, builds the executable with PyInstaller, installs Inno Setup 6, compiles `installer/ModeShift.iss`, and uploads both `ModeShift.exe` and `ModeShiftSetup.exe`. Tagged releases also publish `latest.json` with the portable executable digest and installer digest.

To publish use a public repo `lolipopkins/ModeShift` and push a tag `v0.5.4` matching `src/updater.py:VERSION`. The default update manifest URL points to the latest published release. Do not assume an installer exists before its Windows CI workflow succeeds.

## Release validation checklist
- `ModeShiftSetup.exe` exists and opens on real Windows 10/11 x64.
- Install from scratch; Start menu / optional desktop shortcut launches ModeShift.
- Run updated setup over an old installation and confirm presets/history unchanged.
- Use in-app Update Now to update a previous version while installed.
- Uninstall and verify user data remains, shortcuts disappear.
- Test under standard Windows user permissions without elevation.
- Confirm antivirus/SmartScreen behavior and inspect release artifact hashes.

The build created in this Linux workspace is source + CI configuration, **not an already compiled Windows installer**.
