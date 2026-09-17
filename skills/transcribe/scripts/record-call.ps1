[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet('start','stop','status','list','devices')]
    [string]$Action,

    [Parameter(Position=1)]
    [string]$Name,

    [string]$Device
)

# Mic-only call recorder for Windows: starts/stops an ffmpeg capture in the
# background and writes finished files as mp3 into a recordings folder, ready
# for the transcribe skill to pick up.
#
# Env overrides:
#   RECORD_CALL_DIR      recordings folder (default: ~/work/recordings)
#   RECORD_CALL_FFMPEG   path to ffmpeg.exe (default: "ffmpeg", i.e. PATH)
#   RECORD_CALL_MIC      preferred device name substring to match (e.g. a
#                         headset name); falls back to the first device found
#                         via `record-call devices` if unset or not matched

$ErrorActionPreference = 'Stop'

$RecDir     = if ($env:RECORD_CALL_DIR) { $env:RECORD_CALL_DIR } else { Join-Path $HOME 'work\recordings' }
$StateDir   = Join-Path $RecDir '.state'
$StateFile  = Join-Path $StateDir 'current.json'
$SignalFile = Join-Path $StateDir 'stop.signal'
$GuardExe   = Join-Path $PSScriptRoot '_record-guard.ps1'
$FfmpegExe  = if ($env:RECORD_CALL_FFMPEG) { $env:RECORD_CALL_FFMPEG } else { 'ffmpeg' }

$ffmpegCmd = Get-Command $FfmpegExe -ErrorAction SilentlyContinue
if (-not $ffmpegCmd) { Write-Error "ffmpeg not found ('$FfmpegExe'). Set RECORD_CALL_FFMPEG to its full path, or put ffmpeg on PATH."; exit 1 }
$FfmpegExe = $ffmpegCmd.Source

function Get-AudioDevices {
    # ffmpeg reports its device list on stderr and always exits non-zero for
    # this probe query. With $ErrorActionPreference = 'Stop' (set above),
    # capturing stderr via 2>&1 would otherwise turn each line into a
    # terminating error, so run this one call under 'Continue' instead.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $raw = & $FfmpegExe -hide_banner -list_devices true -f dshow -i dummy 2>&1
    } finally {
        $ErrorActionPreference = $prevEap
    }
    $raw | Select-String -Pattern '"([^"]+)" \(audio\)' |
        ForEach-Object { $_.Matches[0].Groups[1].Value } |
        Select-Object -Unique
}

function Resolve-Mic {
    if ($Device) { return $Device }
    $devices = Get-AudioDevices
    if ($env:RECORD_CALL_MIC) {
        $preferred = $devices | Where-Object { $_ -match [regex]::Escape($env:RECORD_CALL_MIC) } | Select-Object -First 1
        if ($preferred) { return $preferred }
    }
    if ($devices.Count -gt 0) { return $devices[0] }
    throw "No audio input devices found via DirectShow. Run 'record-call devices' to list what's available."
}

function Test-Recording {
    if (-not (Test-Path $StateFile)) { return $null }
    $state = Get-Content $StateFile -Raw | ConvertFrom-Json
    $proc = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -eq 'ffmpeg') { return $state }
    Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    return $null
}

switch ($Action) {
    'devices' {
        Get-AudioDevices | ForEach-Object { Write-Host $_ }
    }

    'start' {
        $running = Test-Recording
        if ($running) {
            Write-Host "Already recording: $($running.outfile) (PID $($running.pid))"
            Write-Host "Use 'record-call stop' first."
            exit 1
        }

        if (-not (Test-Path $RecDir)) { New-Item -ItemType Directory -Path $RecDir -Force | Out-Null }
        if (-not (Test-Path $StateDir)) { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }

        $mic = Resolve-Mic
        $stamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
        $slug = if ($Name) {
            (($Name -replace '[^a-zA-Z0-9-]','-') -replace '-+','-').Trim('-').ToLower()
        } else { 'recording' }
        if (-not $slug) { $slug = 'recording' }
        $outfile = Join-Path $RecDir "${stamp}_${slug}.mp3"

        $ffArgs = "-y -hide_banner -loglevel warning -f dshow -i `"audio=$mic`" -ac 1 -ar 16000 -b:a 48k -c:a libmp3lame `"$outfile`""

        # Write guard config (avoids Windows command-line quoting headaches).
        $configFile = Join-Path $StateDir 'guard-config.json'
        @{
            FfmpegExe  = $FfmpegExe
            FfArgs     = $ffArgs
            StateFile  = $StateFile
            SignalFile = $SignalFile
            OutFile    = $outfile
            Mic        = $mic
        } | ConvertTo-Json | Set-Content $configFile

        Start-Process -FilePath 'powershell.exe' `
            -ArgumentList @('-NoProfile','-File',$GuardExe,'-ConfigFile',$configFile) `
            -WindowStyle Hidden | Out-Null

        # Wait briefly for guard to write state file
        $deadline = (Get-Date).AddSeconds(5)
        while ((-not (Test-Path $StateFile)) -and ((Get-Date) -lt $deadline)) {
            Start-Sleep -Milliseconds 150
        }
        if (-not (Test-Path $StateFile)) {
            Write-Host "Guard did not start (no state file after 5s). Check that ffmpeg is reachable."
            exit 1
        }

        $state = Get-Content $StateFile -Raw | ConvertFrom-Json
        # Confirm ffmpeg is still alive
        Start-Sleep -Milliseconds 400
        $alive = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
        if (-not $alive) {
            Write-Host "ffmpeg exited immediately. Likely cause: bad device name or busy mic."
            Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
            exit 1
        }

        Write-Host "Recording started"
        Write-Host "  Mic:    $mic"
        Write-Host "  Output: $outfile"
        Write-Host "  Stop:   record-call stop"
    }

    'stop' {
        if (-not (Test-Path $StateFile)) { Write-Host "Not recording."; exit 1 }
        $state = Get-Content $StateFile -Raw | ConvertFrom-Json

        # Drop the signal file; the guard will write 'q' to ffmpeg and clean up.
        New-Item -ItemType File -Path $SignalFile -Force | Out-Null

        $deadline = (Get-Date).AddSeconds(12)
        while ((Test-Path $StateFile) -and ((Get-Date) -lt $deadline)) {
            Start-Sleep -Milliseconds 200
        }
        if (Test-Path $StateFile) {
            Write-Host "Guard did not respond within 12s. Force-killing."
            $proc = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
            if ($proc) { Stop-Process -Id $state.pid -Force }
            Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
            Remove-Item $SignalFile -Force -ErrorAction SilentlyContinue
        }

        $duration = (Get-Date) - ([datetime]$state.started)
        Write-Host "Stopped."
        Write-Host "  Duration: $($duration.ToString('hh\:mm\:ss'))"
        Write-Host "  File:     $($state.outfile)"
        if (Test-Path $state.outfile) {
            $sizeMB = (Get-Item $state.outfile).Length / 1MB
            Write-Host ("  Size:     {0:N1} MB" -f $sizeMB)
        } else {
            Write-Host "  WARNING: output file not found"
        }
    }

    'status' {
        $running = Test-Recording
        if (-not $running) { Write-Host "Not recording."; return }
        $duration = (Get-Date) - ([datetime]$running.started)
        Write-Host "Recording"
        Write-Host "  Duration: $($duration.ToString('hh\:mm\:ss'))"
        Write-Host "  Mic:      $($running.mic)"
        Write-Host "  Output:   $($running.outfile)"
    }

    'list' {
        $files = Get-ChildItem $RecDir -Filter '*.mp3' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
        if (-not $files) { Write-Host "No recordings in $RecDir"; return }
        $files | ForEach-Object {
            "{0,-44} {1,8:N1} MB  {2:yyyy-MM-dd HH:mm}" -f $_.Name, ($_.Length/1MB), $_.LastWriteTime
        }
    }
}
