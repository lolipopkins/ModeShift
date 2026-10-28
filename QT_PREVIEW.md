# ModeShift Qt frontend (development preview)

This is a **separate experimental frontend** and does not replace the currently installed Windows application. No GitHub Release is triggered by this change.

## Local preview

1. Install Python 3.12 and run `python -m pip install -r requirements-qt-preview.txt`.
2. From the repository root, launch `python src/qt_frontend.py`.
3. Test rendering and controls on Windows before migrating the production entrypoint.

The frontend reuses `Backend`, `TelemetrySampler`, presets and snapshot logic from `src/modeshift.py`. Current preview screens include Dashboard, Optimizations, Presets, Snapshots, Hardware, Settings. Other features (Automation, Unattended, Measurements, and in-app updater) remain in the stable UI until ported and reviewed. The Qt preview's update check intentionally does not install anything.

**Security:** optimization changes still require a confirmation and maintain the legacy backend snapshots. Do not distribute the preview as the official installer until Windows QA, feature parity, and updater tests are complete.
