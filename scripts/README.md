# Desktop App Builds

These scripts build the packaged pywebview desktop app after compiling the React frontend.

## Windows

```powershell
.\scripts\build-windows.ps1
```

Output:

- `backend/dist/VideoNoteAI/VideoNoteAI.exe`
- `backend/dist/VideoNoteAI-win.zip`

Run the app from `backend/dist/VideoNoteAI/VideoNoteAI.exe`. Do not launch files from `backend/build`; that folder only contains PyInstaller intermediates.

## macOS

```bash
bash ./scripts/build-macos.sh
```

Output: `backend/dist/VideoNoteAI.app`; when `hdiutil` is available, the script also creates `backend/dist/VideoNoteAI.dmg` with the app and an `/Applications` shortcut.

macOS build switches:

- `SKIP_FRONTEND=1` reuses the current `frontend/dist`.
- `SKIP_PLAYWRIGHT=1` skips build-time Chromium installation; the app still checks on first launch.
- `SKIP_DMG=1` leaves only `VideoNoteAI.app`.

Optional signing and notarization:

```bash
CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
APPLE_ID="you@example.com" \
APPLE_TEAM_ID="TEAMID" \
APPLE_APP_PASSWORD="app-specific-password" \
bash ./scripts/build-macos.sh
```

If only `CODESIGN_IDENTITY` is set, the app and DMG are signed but not notarized. The app uses `backend/entitlements.mac.plist` for hardened-runtime signing.

## Notes

- The app listens on `127.0.0.1:8483` for the desktop UI and browser extension bridge.
- User data is stored outside the app bundle:
  - Windows: `%APPDATA%/VideoNoteAI` when available, otherwise `~/Documents/VideoNoteAI_Data`.
  - macOS: `~/Library/Application Support/VideoNoteAI`.
- Playwright Chromium is installed during the build unless `SkipPlaywright` or `SKIP_PLAYWRIGHT=1` is used. The packaged app also checks on first launch and installs Chromium into the user data directory if it is missing.

## Extension Checks

```bash
node extension/test-popup.js
node --check extension/background.js
node --check extension/content.js
node --check extension/popup.js
```
