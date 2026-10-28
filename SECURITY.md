# Windows Security and release trust

ModeShift must not instruct anyone to disable Microsoft Defender, turn off SmartScreen, or add blanket antivirus exclusions.

## Current release status
The installer is not yet Authenticode-signed. GitHub build success and SHA-256 verification do not establish publisher trust. Future public distributions should be signed by a verified publisher and tested on Windows with Defender enabled.

## False-positive reports
Users should record the Microsoft Defender detection name, affected path, and protection-history details (without sharing private information). Maintainers should reproduce and review the exact released binary, then submit it to Microsoft's official malware-analysis/false-positive portal. Do not suppress alerts by default.

## Updater
The installed update path launches the SHA-256-verified Inno Setup binary directly, avoiding hidden PowerShell and execution policy bypass. Portable updater still uses a helper and should not be promoted as Defender-compatible without review.

## Future release gating
1. Build Windows binaries from reviewed code in GitHub Actions.
2. Verify the finished installer opens, updates, and restarts on Windows with Defender enabled.
3. Obtain a publisher identity and Authenticode-sign the setup and executable when feasible.
4. Publish immutable artifacts and integrity metadata only after testing.
5. If antivirus detects the binary, investigate and submit for review rather than disabling protection.
