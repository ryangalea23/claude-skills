[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ConfigFile
)

# Background helper spawned by record-call.ps1. Owns the actual ffmpeg
# process so record-call.ps1 can return immediately, and watches for the
# stop signal file to send ffmpeg a clean 'q' (rather than killing it, which
# can leave a corrupt mp3).

$ErrorActionPreference = 'Stop'

$cfg = Get-Content $ConfigFile -Raw | ConvertFrom-Json
$FfmpegExe  = $cfg.FfmpegExe
$FfArgs     = $cfg.FfArgs
$StateFile  = $cfg.StateFile
$SignalFile = $cfg.SignalFile
$OutFile    = $cfg.OutFile
$Mic        = $cfg.Mic

if (Test-Path $SignalFile) { Remove-Item $SignalFile -Force }

$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $FfmpegExe
$psi.Arguments = $FfArgs
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.CreateNoWindow = $true

$proc = [System.Diagnostics.Process]::Start($psi)

@{
    pid       = $proc.Id
    guard_pid = $PID
    outfile   = $OutFile
    started   = (Get-Date).ToString('o')
    mic       = $Mic
} | ConvertTo-Json | Set-Content $StateFile

while (-not $proc.HasExited) {
    if (Test-Path $SignalFile) {
        try { $proc.StandardInput.WriteLine('q') } catch {}
        try { $proc.StandardInput.Flush() } catch {}
        try { $proc.StandardInput.Close() } catch {}
        if (-not $proc.WaitForExit(8000)) {
            try { $proc.Kill() } catch {}
        }
        break
    }
    Start-Sleep -Milliseconds 250
}

try { Remove-Item $SignalFile -Force -ErrorAction SilentlyContinue } catch {}
try { Remove-Item $StateFile  -Force -ErrorAction SilentlyContinue } catch {}
try { Remove-Item $ConfigFile -Force -ErrorAction SilentlyContinue } catch {}
