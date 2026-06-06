param(
    [string]$AppExePath = "",
    [string]$WorkDir = "",
    [int]$MediaPort = 8765,
    [int]$MockApiPort = 8766
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $AppExePath) {
    $AppExePath = Join-Path $RepoRoot "backend\dist\VideoNoteAI\VideoNoteAI.exe"
}
if (-not $WorkDir) {
    $WorkDir = Join-Path $RepoRoot ".e2e\windows-packaged-auto-run"
}

$AppExePath = (Resolve-Path -LiteralPath $AppExePath).Path
$WorkDir = [System.IO.Path]::GetFullPath($WorkDir)
$DataDir = Join-Path $WorkDir "app_data"
$SampleVideo = Join-Path $WorkDir "sample.mp4"
$SampleSpeech = Join-Path $WorkDir "speech.wav"
$MediaServerScript = Join-Path $WorkDir "static_server.py"
$MockApiScript = Join-Path $WorkDir "mock_openai_api.py"
$MediaServerOutLog = Join-Path $WorkDir "static_server.out.log"
$MediaServerErrLog = Join-Path $WorkDir "static_server.err.log"
$MockApiOutLog = Join-Path $WorkDir "mock_openai_api.out.log"
$MockApiErrLog = Join-Path $WorkDir "mock_openai_api.err.log"

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

New-Item -ItemType Directory -Force -Path $WorkDir, $DataDir | Out-Null

$ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffmpeg = if ($ffmpegCommand) { $ffmpegCommand.Source } else { $null }
if (-not $ffmpeg) {
    $ffmpeg = "C:\ffmpeg\bin\ffmpeg.EXE"
}
if (-not (Test-Path -LiteralPath $ffmpeg)) {
    throw "ffmpeg not found; install ffmpeg or add it to PATH"
}

Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.Rate = -2
$speaker.SetOutputToWaveFile($SampleSpeech)
$speaker.Speak("Packaged app local whisper transcript test. The note generation should use the mock language model.")
$speaker.Dispose()

& $ffmpeg -y `
    -f lavfi -i "testsrc=size=320x180:rate=15" `
    -i $SampleSpeech `
    -shortest `
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
"@ | Set-Content -LiteralPath $MediaServerScript -Encoding UTF8

@"
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def _json(self, payload):
        data = json.dumps(payload).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/v1/models':
            self._json({'object': 'list', 'data': [{'id': 'mock-note-model', 'object': 'model'}]})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/v1/chat/completions':
            self._json({
                'id': 'chatcmpl-mock',
                'object': 'chat.completion',
                'choices': [
                    {'index': 0, 'message': {'role': 'assistant', 'content': '# AUTO_RUN_NOTE_OK\n\n- Packaged app full flow passed.'}, 'finish_reason': 'stop'}
                ]
            })
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass

HTTPServer(('127.0.0.1', $MockApiPort), Handler).serve_forever()
"@ | Set-Content -LiteralPath $MockApiScript -Encoding UTF8

$mediaServer = $null
$mockApiServer = $null
try {
    Stop-VideoNoteAI
    Remove-Item -LiteralPath $MediaServerOutLog, $MediaServerErrLog, $MockApiOutLog, $MockApiErrLog -Force -ErrorAction SilentlyContinue
    $mediaServer = Start-Process -FilePath "python" -ArgumentList $MediaServerScript -PassThru -WindowStyle Hidden -RedirectStandardOutput $MediaServerOutLog -RedirectStandardError $MediaServerErrLog
    $mockApiServer = Start-Process -FilePath "python" -ArgumentList $MockApiScript -PassThru -WindowStyle Hidden -RedirectStandardOutput $MockApiOutLog -RedirectStandardError $MockApiErrLog
    Wait-HttpOk -Uri "http://127.0.0.1:$MediaPort/sample.mp4"
    Wait-HttpOk -Uri "http://127.0.0.1:$MockApiPort/v1/models"

    $env:VIDEO_NOTE_DATA_DIR = $DataDir
    $env:TRANSCRIBER_TYPE = "fast-whisper"
    $env:WHISPER_MODEL_SIZE = "tiny"
    $env:WHISPER_DEVICE = "cpu"
    $env:WHISPER_COMPUTE_TYPE = "int8"
    Start-Process -FilePath $AppExePath -WindowStyle Hidden

    $health = Wait-Health
    $token = $health.data.bridgeToken
    if (-not $token) {
        throw "Bridge token missing from health response"
    }

    $activeBody = @{
        provider = "mock-api"
        provider_type = "custom"
        api_key = "local-key"
        base_url = "http://127.0.0.1:$MockApiPort/v1"
        model = "mock-note-model"
        note_style = "simple"
    } | ConvertTo-Json
    Invoke-RestMethod `
        -Method Post `
        -Uri "http://127.0.0.1:8483/api/models/active" `
        -ContentType "application/json" `
        -Body $activeBody `
        -TimeoutSec 10 | Out-Null

    $importBody = @{
        pageUrl = "http://127.0.0.1:$MediaPort/sample.mp4"
        pageTitle = "Packaged AutoRun Sample"
        candidateUrl = "http://127.0.0.1:$MediaPort/sample.mp4"
        formatId = "detected"
        autoRun = $true
    } | ConvertTo-Json
    $import = Invoke-RestMethod `
        -Method Post `
        -Uri "http://127.0.0.1:8483/api/extension/videos/import" `
        -ContentType "application/json" `
        -Headers @{ "X-AInote-Bridge-Token" = $token } `
        -Body $importBody `
        -TimeoutSec 10

    $job = Wait-Job -JobId $import.data.jobId -Token $token -Seconds 180
    if ($job.data.status -ne "completed") {
        throw "Job failed: $($job.data.error)"
    }

    $task = Invoke-RestMethod -Uri "http://127.0.0.1:8483/api/task/$($job.data.taskId)" -TimeoutSec 10
    if ($task.data.status -ne "completed") {
        throw "Task did not complete: $($task.data.status)"
    }
    if (-not $task.data.markdown -or -not $task.data.markdown.Contains("AUTO_RUN_NOTE_OK")) {
        throw "Generated markdown did not come from mock model"
    }
    if (-not $task.data.transcript -or $task.data.transcript.segments.Count -lt 1) {
        throw "Local faster-whisper transcript missing from completed task"
    }

    $process = Get-Process -Name VideoNoteAI -ErrorAction SilentlyContinue | Select-Object -First 1
    [pscustomobject]@{
        healthCode = $health.code
        dataDir = $DataDir
        jobStatus = $job.data.status
        jobProgress = $job.data.progress
        taskId = $job.data.taskId
        taskStatus = $task.data.status
        markdownLength = $task.data.markdown.Length
        transcriptSegments = $task.data.transcript.segments.Count
        windowTitle = $process.MainWindowTitle
        windowHandle = $process.MainWindowHandle
    } | ConvertTo-Json
}
finally {
    Stop-VideoNoteAI
    Remove-Item Env:\VIDEO_NOTE_DATA_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:\TRANSCRIBER_TYPE -ErrorAction SilentlyContinue
    Remove-Item Env:\WHISPER_MODEL_SIZE -ErrorAction SilentlyContinue
    Remove-Item Env:\WHISPER_DEVICE -ErrorAction SilentlyContinue
    Remove-Item Env:\WHISPER_COMPUTE_TYPE -ErrorAction SilentlyContinue
    if ($mediaServer -and -not $mediaServer.HasExited) {
        Stop-Process -Id $mediaServer.Id -Force
    }
    if ($mockApiServer -and -not $mockApiServer.HasExited) {
        Stop-Process -Id $mockApiServer.Id -Force
    }
}
