param(
    [switch]$SkipFrontend,
    [switch]$SkipPlaywright,
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontendDir = Join-Path $RepoRoot "frontend"
$BackendDir = Join-Path $RepoRoot "backend"
$BackendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$DistPath = Join-Path $BackendDir "dist\VideoNoteAI"
$ZipPath = Join-Path $BackendDir "dist\VideoNoteAI-win.zip"
$PyInstallerBuildPath = Join-Path $BackendDir "build\video_note_ai"
$AppExePath = Join-Path $DistPath "VideoNoteAI.exe"

function Remove-GeneratedPath {
    param([string]$PathToRemove)

    if (-not (Test-Path -LiteralPath $PathToRemove)) {
        return
    }

    $resolvedTarget = (Resolve-Path -LiteralPath $PathToRemove).Path
    if (-not $resolvedTarget.StartsWith($RepoRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside repo: $resolvedTarget"
    }

    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force -ErrorAction Stop
}

Write-Host "Building VideoNoteAI for Windows..." -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $BackendPython)) {
    throw "Python virtual environment not found at $BackendPython. Create it with: python -m venv backend\.venv"
}

if (-not $SkipFrontend) {
    Push-Location $FrontendDir
    try {
        if (-not (Test-Path "node_modules")) {
            npm install
        }
        npm run build
    }
    finally {
        Pop-Location
    }
}

Push-Location $BackendDir
try {
    & $BackendPython -m pip install -r requirements.txt
    if (-not $SkipPlaywright) {
        & $BackendPython -m playwright install chromium
    }
    Remove-GeneratedPath $PyInstallerBuildPath
    Remove-GeneratedPath $DistPath
    if (-not $SkipZip) {
        Remove-GeneratedPath $ZipPath
    }
    & $BackendPython -m PyInstaller --clean --noconfirm video_note_ai.spec
}
finally {
    Pop-Location
}

if (-not $SkipZip) {
    Compress-Archive -Path (Join-Path $DistPath "*") -DestinationPath $ZipPath -Force
    Write-Host "Windows zip package created at $ZipPath" -ForegroundColor Green
}

Remove-GeneratedPath $PyInstallerBuildPath

Write-Host "Windows app bundle created at $DistPath" -ForegroundColor Green
Write-Host "Run the app with $AppExePath" -ForegroundColor Green
