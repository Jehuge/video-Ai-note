# VideoNoteAI Desktop + Extension Release Checklist

Use this checklist before claiming the Windows/macOS desktop app and browser extension are release-ready.

## Build Artifacts

### Windows

- Run `npm run build` in `frontend`.
- Run `.\scripts\build-windows.ps1 -SkipFrontend -SkipPlaywright` from the repo root.
- Verify `backend/dist/VideoNoteAI/VideoNoteAI.exe` exists.
- Verify `backend/dist/VideoNoteAI-win.zip` exists.
- Start `backend/dist/VideoNoteAI/VideoNoteAI.exe`.
- Confirm the process has a visible window titled `Video Note AI`.
- Confirm `GET http://127.0.0.1:8483/api/extension/health` returns `code: 200`.
- Confirm `dataDir` is under `%APPDATA%\VideoNoteAI` or the configured `VIDEO_NOTE_DATA_DIR`.
- Close the app and confirm no `VideoNoteAI` process remains.

### macOS

- Run `npm run build` in `frontend`.
- Run `bash ./scripts/build-macos.sh` on macOS 12+.
- Verify `backend/dist/VideoNoteAI.app` exists.
- Verify `backend/dist/VideoNoteAI.dmg` exists unless `SKIP_DMG=1` was used.
- Open the `.app` from Finder.
- Confirm the app has a visible window titled `Video Note AI`.
- Confirm `GET http://127.0.0.1:8483/api/extension/health` returns `code: 200`.
- Confirm `dataDir` is `~/Library/Application Support/VideoNoteAI` or the configured `VIDEO_NOTE_DATA_DIR`.
- If release signing is enabled, run `codesign --verify --deep --strict backend/dist/VideoNoteAI.app`.
- If notarization is enabled, run `spctl -a -vv backend/dist/VideoNoteAI.app`.

## Automated Tests

- Run `python -m unittest discover backend\tests` on Windows.
- Run `python3 -m unittest discover backend/tests` on macOS.
- Run `python -m compileall backend\app`.
- Run `npm run build` in `frontend`.
- Run:
  - `node extension/test-popup.js`
  - `node --check extension/background.js`
  - `node --check extension/content.js`
  - `node --check extension/popup.js`
  - `node --check extension/test-popup.js`

## Extension Manual Checks

- Load `extension/` as an unpacked extension in Chrome or Edge.
- With the app closed, open the popup and confirm it reports that AInote is not running.
- Start the app and confirm the popup reports a connected app.
- Test a page with no video and confirm a clear no-video state.
- Test a direct `.mp4` page and confirm a candidate is shown.
- Test a public HLS `.m3u8` page and confirm a candidate is shown.
- Test a DASH `.mpd` page and confirm a candidate is shown.
- Test a page with multiple candidates and confirm quality/candidate selection works.
- Enable `Site cookies` and confirm cookies are sent only after user opt-in.
- Confirm wrong or missing bridge token requests to protected extension APIs are rejected.

## End-to-End Flow

Run this once on Windows and once on macOS:

- Start the desktop app.
- Configure a working model in the app.
- Load the extension in Chrome or Edge.
- Open a public test video page.
- Select a detected candidate/quality in the extension.
- Click generate video note.
- Confirm `/api/extension/videos/import` creates a job.
- Confirm `/api/extension/jobs/{jobId}` reaches `completed`.
- Confirm the downloaded file appears in the app uploads directory.
- Confirm a `video_tasks` row is created with `source=web`.
- Confirm the task runs through audio extraction, transcription, and note generation.
- Confirm the generated note appears in the app.

## Regression Checks

- Local file upload still creates a task.
- Manual extract, transcribe, and summarize steps still work.
- A completed transcription shows `transcribed` or a completed transcript state, not an endless spinner.
- Model list and model connection tests do not raise `Client.__init__() got an unexpected keyword argument 'proxy'`.
- Bilibili download page still loads.
- Video library still lists local video files.
- Export PDF still works for a completed note.

## Known Non-Goals

- Do not claim DRM, encrypted streams, captchas, paywalls, or service-rule bypass support.
- Firefox extension support is not part of the first release.
- macOS Gatekeeper release readiness requires signing and notarization evidence from an Apple Developer account.
