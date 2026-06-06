#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_DIR="$REPO_ROOT/backend"
PYINSTALLER_BUILD_DIR="$BACKEND_DIR/build/video_note_ai"
APP_PATH="$BACKEND_DIR/dist/VideoNoteAI.app"
DMG_PATH="$BACKEND_DIR/dist/VideoNoteAI.dmg"
DMG_STAGING_DIR="$BACKEND_DIR/build/dmg"

SKIP_FRONTEND="${SKIP_FRONTEND:-0}"
SKIP_PLAYWRIGHT="${SKIP_PLAYWRIGHT:-0}"
SKIP_DMG="${SKIP_DMG:-0}"
CODESIGN_IDENTITY="${CODESIGN_IDENTITY:-}"
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-}"
ENTITLEMENTS_FILE="$BACKEND_DIR/entitlements.mac.plist"

remove_generated_path() {
  local target="$1"
  if [[ ! -e "$target" ]]; then
    return
  fi

  local resolved_target
  resolved_target="$(cd "$(dirname "$target")" && pwd)/$(basename "$target")"
  case "$resolved_target" in
    "$REPO_ROOT"/*) rm -rf "$resolved_target" ;;
    *) echo "Refusing to remove path outside repo: $resolved_target" >&2; exit 1 ;;
  esac
}

echo "Building VideoNoteAI for macOS..."

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must run on macOS because PyInstaller .app and hdiutil DMG builds are platform-specific." >&2
  exit 1
fi

if [[ "$SKIP_FRONTEND" != "1" ]]; then
  cd "$FRONTEND_DIR"
  if [[ ! -d node_modules ]]; then
    npm install
  fi
  npm run build
fi

cd "$BACKEND_DIR"
python3 -m pip install -r requirements.txt
if [[ "$SKIP_PLAYWRIGHT" != "1" ]]; then
  python3 -m playwright install chromium
fi
remove_generated_path "$PYINSTALLER_BUILD_DIR"
remove_generated_path "$APP_PATH"
remove_generated_path "$DMG_PATH"
remove_generated_path "$DMG_STAGING_DIR"
CODESIGN_IDENTITY="$CODESIGN_IDENTITY" pyinstaller --clean --noconfirm video_note_ai.spec

if [[ -n "$CODESIGN_IDENTITY" && -d "$APP_PATH" ]]; then
  echo "Signing app with identity: $CODESIGN_IDENTITY"
  codesign --force --deep --options runtime --entitlements "$ENTITLEMENTS_FILE" --sign "$CODESIGN_IDENTITY" "$APP_PATH"
fi

if [[ -d "$APP_PATH" && "$SKIP_DMG" != "1" ]] && command -v hdiutil >/dev/null 2>&1; then
  rm -f "$DMG_PATH"
  remove_generated_path "$DMG_STAGING_DIR"
  mkdir -p "$DMG_STAGING_DIR"
  cp -R "$APP_PATH" "$DMG_STAGING_DIR/"
  ln -s /Applications "$DMG_STAGING_DIR/Applications"
  hdiutil create -volname "VideoNoteAI" -srcfolder "$DMG_STAGING_DIR" -ov -format UDZO "$DMG_PATH"
  echo "macOS DMG created at $DMG_PATH"
  if [[ -n "$CODESIGN_IDENTITY" ]]; then
    codesign --force --sign "$CODESIGN_IDENTITY" "$DMG_PATH"
  fi
else
  echo "macOS app bundle created at $APP_PATH"
fi

if [[ -n "$APPLE_ID" && -n "$APPLE_TEAM_ID" && -n "$APPLE_APP_PASSWORD" && -f "$DMG_PATH" ]]; then
  echo "Submitting DMG for notarization..."
  xcrun notarytool submit "$DMG_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --wait
  xcrun stapler staple "$DMG_PATH"
  echo "macOS DMG notarized and stapled at $DMG_PATH"
fi

remove_generated_path "$PYINSTALLER_BUILD_DIR"
remove_generated_path "$DMG_STAGING_DIR"
echo "Run the app from $APP_PATH"
