# Install the locked native Windows Python environment; optionally install Node tools.
param([switch]$Development)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if ($env:OS -ne 'Windows_NT') {
        throw 'Run setup.ps1 with native Windows PowerShell.'
    }

    New-Item -ItemType Directory -Force .tmp | Out-Null
    $uvVersion = '0.13.0'
    $uv = Join-Path $PSScriptRoot '.tmp/uv-windows/uv.exe'
    if (-not (Test-Path $uv)) {
        $installedUv = Get-Command uv -ErrorAction SilentlyContinue
        if ($installedUv) {
            $uv = $installedUv.Source
        } else {
            $archive = Join-Path $PSScriptRoot '.tmp/uv-windows.zip'
            Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/astral-sh/uv/releases/download/$uvVersion/uv-x86_64-pc-windows-msvc.zip" -OutFile $archive
            Expand-Archive -Path $archive -DestinationPath .tmp/uv-windows -Force
        }
    }
    $actualUv = & $uv --version
    if ($LASTEXITCODE -ne 0 -or $actualUv -notmatch "^uv $([regex]::Escape($uvVersion))( |$)") {
        throw "Expected uv $uvVersion; found: $actualUv"
    }
    Write-Host $actualUv

    if ($Development) {
        $nodeVersion = (Get-Content .node-version -Raw).Trim()
        if (-not (Get-Command node -ErrorAction SilentlyContinue) -or
            -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
            throw "Install Node.js $nodeVersion with bundled npm and rerun setup.ps1 -Development."
        }
        $actualNode = & node --version
        if ($LASTEXITCODE -ne 0 -or $actualNode -ne "v$nodeVersion") {
            throw "Expected Node.js $nodeVersion; found: $actualNode"
        }
    }

    $pythonVersion = (Get-Content .python-version -Raw).Trim()
    & $uv python install $pythonVersion
    if ($LASTEXITCODE -ne 0) { throw 'Python installation failed.' }
    & $uv sync --locked --all-extras --group dev
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

    if ($Development) {
        & npm.cmd ci --no-audit --no-fund --cache "$PSScriptRoot/.tmp/npm-cache"
        if ($LASTEXITCODE -ne 0) { throw 'Node dependency installation failed.' }
    }
    Write-Host 'Environment ready. Start the application with ./start.ps1.'
} finally {
    Pop-Location
}
