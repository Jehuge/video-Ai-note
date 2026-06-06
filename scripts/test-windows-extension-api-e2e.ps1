param(
    [string]$AppExePath = "",
    [string]$WorkDir = "",
    [int]$MediaPort = 8765,
    [switch]$KeepData
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $AppExePath) {
    $AppExePath = Join-Path $RepoRoot "backend\dist\VideoNoteAI\VideoNoteAI.exe"
}
if (-not $WorkDir) {
    $WorkDir = Join-Path $RepoRoot ".e2e\windows-extension-api"
}

$AppExePath = (Resolve-Path -LiteralPath $AppExePath).Path
$WorkDir = [System.IO.Path]::GetFullPath($WorkDir)
$DataDir = Join-Path $WorkDir "app_data"
$SampleVideo = Join-Path $WorkDir "sample.mp4"
$ServerScript = Join-Path $WorkDir "static_server.py"

function Stop-VideoNoteAI {
    Get-Process -Name VideoNoteAI -ErrorAction SilentlyContinue | Stop-Process -Force
}

function Wait-Health {
    param([int]$Seconds = 45)

    for ($i = 0; $i -lt $Seconds; $i++) {
        try {
            return Invoke-RestMethod -Uri "http://127.0.0.1:8483/api/extension/health" -TimeoutSec 2
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "App health endpoint did not become ready"
}

New-Item -ItemType Directory -Force -Path $WorkDir, $DataDir | Out-Null

$ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffmpeg = if ($ffmpegCommand) { $ffmpegCommand.Source } else { $null }
if (-not $ffmpeg) {
    $ffmpeg = "C:\ffmpeg\bin\ffmpeg.EXE"
}
if (-not (Test-Path -LiteralPath $ffmpeg)) {
    throw "ffmpeg not found; install ffmpeg or add it to PATH"
}

& $ffmpeg -y `
    -f lavfi -i "testsrc=size=320x180:rate=15" `
    -f lavfi -i "sine=frequency=440:sample_rate=16000" `
    -t 1 `
    -c:v libx264 -pix_fmt yuv420p `
    -c:a aac `
    $SampleVideo | Out-Null

@"
import http.server
import os
import socketserver

os.chdir(r'$WorkDir')

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(('127.0.0.1', $MediaPort), Handler) as httpd:
    httpd.serve_forever()
"@ | Set-Content -Path $ServerScript -Encoding UTF8

$server = $null
try {
    Stop-VideoNoteAI
    $server = Start-Process -FilePath python -ArgumentList @($ServerScript) -PassThru -WindowStyle Hidden

    $env:VIDEO_NOTE_DATA_DIR = $DataDir
    $app = Start-Process -FilePath $AppExePath -PassThru
    try {
        $health = Wait-Health
        $token = $health.data.bridgeToken
        if (-not $token) {
            throw "Health response did not include bridge token"
        }

        $headers = @{ "X-AInote-Bridge-Token" = $token }
        $videoUrl = "http://127.0.0.1:$MediaPort/sample.mp4"
        $stream = @{
            url = $videoUrl
            mimeType = "video/mp4"
            label = "Direct MP4"
            height = 180
            source = "e2e"
        }

        $resolveBody = @{
            pageUrl = $videoUrl
            pageTitle = "Local E2E Sample"
            detectedStreams = @($stream)
        } | ConvertTo-Json -Depth 6
        $resolve = Invoke-RestMethod `
            -Uri "http://127.0.0.1:8483/api/extension/videos/resolve" `
            -Method Post `
            -Body $resolveBody `
            -ContentType "application/json" `
            -Headers $headers `
            -TimeoutSec 30
        if (($resolve.data.candidates | Measure-Object).Count -lt 1) {
            throw "Resolve returned no candidates"
        }

        $importBody = @{
            pageUrl = $videoUrl
            pageTitle = "Local E2E Sample"
            detectedStreams = @($stream)
            candidateId = "e2e-direct"
            candidateUrl = $videoUrl
            formatId = "detected"
            autoRun = $false
            screenshot = $false
        } | ConvertTo-Json -Depth 6
        $import = Invoke-RestMethod `
            -Uri "http://127.0.0.1:8483/api/extension/videos/import" `
            -Method Post `
            -Body $importBody `
            -ContentType "application/json" `
            -Headers $headers `
            -TimeoutSec 30

        $jobId = $import.data.jobId
        $job = $null
        for ($i = 0; $i -lt 80; $i++) {
            $job = Invoke-RestMethod -Uri "http://127.0.0.1:8483/api/extension/jobs/$jobId" -Headers $headers -TimeoutSec 5
            if ($job.data.status -in @("completed", "failed")) {
                break
            }
            Start-Sleep -Milliseconds 500
        }
        if ($job.data.status -ne "completed") {
            throw "Job did not complete: $($job.data.status) $($job.data.error)"
        }

        $taskId = $job.data.taskId
        $task = Invoke-RestMethod -Uri "http://127.0.0.1:8483/api/task/$taskId" -TimeoutSec 10
        if ($task.data.source -ne "web") {
            throw "Expected task source=web, got $($task.data.source)"
        }

        $uploads = Get-ChildItem (Join-Path $DataDir "uploads") -File
        if (($uploads | Measure-Object).Count -lt 1) {
            throw "No imported upload file was created"
        }

        $process = Get-Process -Id $app.Id -ErrorAction SilentlyContinue
        [pscustomobject]@{
            healthCode = $health.code
            dataDir = $health.data.dataDir
            resolveCandidates = ($resolve.data.candidates | Measure-Object).Count
            jobStatus = $job.data.status
            jobProgress = $job.data.progress
            taskId = $taskId
            taskStatus = $task.data.status
            taskSource = $task.data.source
            taskSourceUrl = $task.data.source_url
            uploadCount = ($uploads | Measure-Object).Count
            windowTitle = $process.MainWindowTitle
            windowHandle = $process.MainWindowHandle
        } | ConvertTo-Json -Depth 6
    }
    finally {
        Stop-VideoNoteAI
        Remove-Item Env:\VIDEO_NOTE_DATA_DIR -ErrorAction SilentlyContinue
    }
}
finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
    if (-not $KeepData) {
        Remove-Item -LiteralPath $WorkDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
