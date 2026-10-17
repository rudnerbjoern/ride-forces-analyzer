# Start the installed application without downloading or changing dependencies.
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if ($env:OS -ne 'Windows_NT') {
        throw 'Run start.ps1 with native Windows PowerShell.'
    }
    $python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path $python)) {
        throw 'Python environment missing. Run ./setup.ps1 first.'
    }
    & $python -m ride_forces_analyzer
    $applicationExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $applicationExitCode
