## v0.6.0 (development; Windows verification pending)
- Update toast, theme selector, basic approval-first Smart Scan, installer-aware updating.
- Added installer upgrade tests.

# Changelog

## v0.5.4 (installer infrastructure)
- Added Inno Setup 6 per-user installer with Start menu and optional desktop shortcut.
- Updated Windows CI and release workflows to generate `ModeShiftSetup.exe` alongside portable `ModeShift.exe`.
- Release manifest now exposes optional installer link + checksum while retaining the existing EXE update feed.
- Kept AppData preferences/presets/measurements separate from app installation and uninstall.
- Updated app version; installer still requires Windows CI compilation and validation.

# Changelog

## v0.5.0 — UI refresh, dashboard controls, and optional updater

- Refreshed dark/navy and amber interface styling, typography, spacing, and combobox appearance.
- Reorganized the dashboard with a prominent quick-mode picker, workload descriptions, direct shortcuts to all optimizations and backups, and Auto Mode access.
- Dashboard Auto Mode toggle uses the existing opt-in, workload-aware **power-plan-only** automation and links to advanced rules; registry changes are never automatic.
- Added Settings release URL, manual check, release notes, explicit download/install approval, HTTPS validation, and SHA-256 verification.
- Portable EXE update replacement retains the old executable as `ModeShift.previous.exe`; app state stays in `%LOCALAPPDATA%`.
- Added `UPDATE_GUIDE.md` explaining publisher requirements and limitations.
- Added 3 updater unit tests, 17 passing tests total in Linux simulation; smoke-tested all eight app screens under Xvfb.

## v0.4.0

- Automatic power-plan matching, safer snapshot collision checks, resource trend graphs, recorded measurements, and eight navigation screens.

## v0.5.1 — GPU detection hotfix
- Fixed GPU dashboard misreporting when the NVIDIA driver CLI is not installed or available.
- Added Windows-native adapter discovery and best-effort GPU engine performance-counter fallback for AMD, Intel and NVIDIA cards.
- When using Windows counters, shows *peak GPU engine load* rather than incorrectly labeling it total GPU utilization.
- Missing VRAM or temperature readings are now displayed as unavailable instead of crashing the Hardware page.
- Added GPU fallback regression tests. Windows hardware validation is still required.

## 0.5.2 — Unattended Dev + Rendering guard
- Dedicated Unattended section and dashboard shortcut for overlapping Claude, Blender and Roblox Studio workflows.
- Opt-in, configurable RAM/VRAM/disk pressure warnings and local JSON Lines heartbeat/incident log.
- No automatic process termination, suspension, GPU clock manipulation or unverified crash-prevention claims.
- Guard only monitors while ModeShift remains open; cannot control Claude job scheduling or guarantee crash prevention.
