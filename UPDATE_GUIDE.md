# ModeShift v0.5 update publishing guide

ModeShift's update system is now included in Settings, but no official hosted update feed is configured or operated by this ZIP. The user or release publisher must host releases.

## Release setup

1. Build `ModeShift.exe` with `build_exe.bat` on Windows.
2. Publish the exact EXE file to an HTTPS location (for example, a public GitHub Release asset).
3. Compute the SHA-256 digest of that file using `Get-FileHash -Algorithm SHA256 .\dist\ModeShift.exe` in PowerShell.
4. Publish a separate HTTPS `latest.json` file containing the exact EXE download URL and digest, using this schema:

```json
{
  "version": "0.6.0",
  "url": "https://YOUR-RELEASE-HOST/ModeShift.exe",
  "sha256": "REPLACE_WITH_64_HEX_CHARACTERS_FROM_GET_FILE_HASH",
  "notes": "Release notes here"
}
```

5. On the installed application's Settings page, enter the HTTPS URL for the `latest.json` manifest and choose **Save release URL**. Choose **Check for updates**, then review and approve an available update.

## Behavior and limitations

- The updater downloads only from HTTPS, bounds manifest and EXE sizes, and verifies SHA-256 before offering replacement. SHA-256 guards accidental/corrupted downloads, but **does not authenticate a malicious release publisher**: you must trust the manifest host and secure its publishing access. Code signing should be added before public distribution.
- The updater is intended for user-writable **portable EXEs**; it cannot silently replace Program Files installations, installed packages, or signed installers.
- It waits for the application to exit, renames the prior EXE to `ModeShift.previous.exe`, moves the verified downloaded EXE into place, and relaunches. A failed move attempts to restore the previous EXE. This is not a full transactional installer or crash-proof rollback. You can manually restore `.previous.exe`.
- All existing application preferences and snapshots live under `%LOCALAPPDATA%\ModeShift` and are not deleted by replacement.
- Requires internet access for an update check and download. No update URL is predefined; the application is usable offline.
- If an update happens to require a data-schema migration, this code does not yet provide a complete migration management system.
