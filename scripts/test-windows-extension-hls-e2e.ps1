param(
    [string]$AppExePath = "",
    [string]$WorkDir = "",
    [int]$MediaPort = 8777
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $AppExePath) {
    $AppExePath = Join-Path $RepoRoot "backend\dist\VideoNoteAI\VideoNoteAI.exe"
}
if (-not $WorkDir) {
    $WorkDir = Join-Path $RepoRoot ".e2e\windows-extension-hls"
}

$AppExePath = (Resolve-Path -LiteralPath $AppExePath).Path
$WorkDir = [System.IO.Path]::GetFullPath($WorkDir)
$DataDir = Join-Path $WorkDir "app_data"
$MediaDir = Join-Path $WorkDir "media"
$ServerScript = Join-Path $WorkDir "static_server.py"

function Stop-VideoNoteAI {
    Get-Process -Name VideoNoteAI -ErrorAction SilentlyContinue | Stop-Process -Force
}

function Wait-Health {
    param([int]$Seconds = 60)

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

function Wait-HttpOk {
    param(
        [string]$Uri,
        [int]$Seconds = 20
    )

    for ($i = 0; $i -lt $Seconds; $i++) {
        try {
            Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2 | Out-Null
            return
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "Endpoint did not become ready: $Uri"
}

function Wait-Job {
    param(
        [string]$JobId,
        [string]$Token,
        [int]$Seconds = 90
    )

    for ($i = 0; $i -lt $Seconds; $i++) {
        $job = Invoke-RestMethod `
            -Uri "http://127.0.0.1:8483/api/extension/jobs/$JobId" `
            -Headers @{ "X-AInote-Bridge-Token" = $Token } `
            -TimeoutSec 5
        if ($job.data.status -in @("completed", "failed")) {
            return $job
        }
        Start-Sleep -Seconds 1
    }
    throw "Job did not finish within $Seconds seconds"
}

New-Item -ItemType Directory -Force -Path $WorkDir, $DataDir, $MediaDir | Out-Null
Get-ChildItem -LiteralPath $MediaDir -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

$ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffmpeg = if ($ffmpegCommand) { $ffmpegCommand.Source } else { $null }
if (-not $ffmpeg) {
    $ffmpeg = "C:\ffmpeg\bin\ffmpeg.EXE"
}
if (-not (Test-Path -LiteralPath $ffmpeg)) {
    throw "ffmpeg not found; install ffmpeg or add it to PATH"
}

& $ffmpeg -y `
    -f lavfi -i "testsrc=size=426x240:rate=15" `
    -f lavfi -i "sine=frequency=440:sample_rate=16000" `
    -t 2 `
    -c:v libx264 -pix_fmt yuv420p `
    -c:a aac `
    -f hls `
    -hls_time 1 `
    -hls_list_size 0 `
    -hls_segment_filename (Join-Path $MediaDir "seg_%03d.ts") `
    (Join-Path $MediaDir "master.m3u8") | Out-Null

@"
import http.server
import os
import socketserver

os.chdir(r'$MediaDir')

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

with socketserver.TCPServer(('127.0.0.1', $MediaPort), Handler) as httpd:
    httpd.serve_forever()
"@ | Set-Content -LiteralPath $ServerScript -Encoding UTF8

$serverJob = $null
try {
    Stop-VideoNoteAI
    $serverJob = Start-Job -ScriptBlock {
        param($ScriptPath)
        python $ScriptPath
    } -ArgumentList $ServerScript
    $manifestUrl = "http://127.0.0.1:$MediaPort/master.m3u8"
    Wait-HttpOk -Uri $manifestUrl

    $env:VIDEO_NOTE_DATA_DIR = $DataDir
    Start-Process -FilePath $AppExePath -WindowStyle Hidden
    $health = Wait-Health
    $token = $health.data.bridgeToken
    if (-not $token) {
        throw "Health response did not include bridge token"
    }

    $headers = @{ "X-AInote-Bridge-Token" = $token }
    $stream = @{
        url = $manifestUrl
        mimeType = "application/vnd.apple.mpegurl"
        label = "HLS stream"
        source = "e2e"
    }

    $resolveBody = @{
        pageUrl = "http://127.0.0.1:$MediaPort/watch"
        pageTitle = "Local HLS E2E"
        detectedStreams = @($stream)
    } | ConvertTo-Json -Depth 8

    $resolve = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8483/api/extension/videos/resolve" `
        -Method Post `
        -Body $resolveBody `
        -ContentType "application/json" `
        -Headers $headers `
        -TimeoutSec 45

    $candidates = @($resolve.data.candidates)
    if ($candidates.Count -lt 1) {
        throw "Resolve returned no candidates"
    }

    $hlsCandidate = $candidates | Where-Object {
        $_.sourceUrl -eq $manifestUrl -or ((@($_.formats) | Where-Object { $_.protocol -match "m3u8" }).Count -gt 0)
    } | Select-Object -First 1
    if (-not $hlsCandidate) {
        throw "Resolve did not return an HLS candidate"
    }

    $format = @($hlsCandidate.formats)[0]
    $importBody = @{
        pageUrl = "http://127.0.0.1:$MediaPort/watch"
        pageTitle = "Local HLS E2E"
        detectedStreams = @($stream)
        candidateId = $hlsCandidate.id
        candidateUrl = $hlsCandidate.sourceUrl
        formatId = $format.formatId
        autoRun = $false
        screenshot = $false
    } | ConvertTo-Json -Depth 8

    $import = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8483/api/extension/videos/import" `
        -Method Post `
        -Body $importBody `
        -ContentType "application/json" `
        -Headers $headers `
        -TimeoutSec 30

    $job = Wait-Job -JobId $import.data.jobId -Token $token -Seconds 90
    if ($job.data.status -ne "completed") {
        throw "Job did not complete: $($job.data.status) $($job.data.error)"
    }

    $uploads = Get-ChildItem (Join-Path $DataDir "uploads") -File
    if (($uploads | Measure-Object).Count -lt 1) {
        throw "No imported upload file was created"
    }

    [pscustomobject]@{
        healthCode = $health.code
        dataDir = $health.data.dataDir
        resolveCandidates = $candidates.Count
        selectedCandidate = $hlsCandidate.id
        selectedFormat = $format.formatId
        selectedProtocol = $format.protocol
        jobStatus = $job.data.status
        jobProgress = $job.data.progress
        taskId = $job.data.taskId
        uploadCount = ($uploads | Measure-Object).Count
        uploadNames = ($uploads | ForEach-Object { $_.Name }) -join ","
    } | ConvertTo-Json
}
finally {
    Stop-VideoNoteAI
    Remove-Item Env:\VIDEO_NOTE_DATA_DIR -ErrorAction SilentlyContinue
    if ($serverJob) {
        Stop-Job -Job $serverJob -ErrorAction SilentlyContinue
        Remove-Job -Job $serverJob -Force -ErrorAction SilentlyContinue
    }
}
