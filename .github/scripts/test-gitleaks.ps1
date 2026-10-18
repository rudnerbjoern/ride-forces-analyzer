# Exercise the pinned scanner against clean and deleted synthetic-secret history.
# Copyright (c) 2026 Björn Rudner. SPDX-License-Identifier: GPL-3.0-or-later
$ErrorActionPreference = 'Stop'
$scanner = (Resolve-Path '.tmp/gitleaks/gitleaks.exe').Path
$config = (Resolve-Path '.tmp/gitleaks/rules.toml').Path
$ignore = (Resolve-Path '.tmp/gitleaks/empty-ignore').Path
$directory = Join-Path (Resolve-Path '.tmp').Path ('scanner-probe-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $directory | Out-Null
$repository = Join-Path $directory 'repository'
New-Item -ItemType Directory -Path $repository | Out-Null
function Invoke-ProbeGit {
    & git -C $repository @args *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic Git fixture failed.' }
}
function Invoke-ProbeScan {
    $arguments = @('git', '--log-opts=--all', "--config=$config",
        "--gitleaks-ignore-path=$ignore", '--ignore-gitleaks-allow', '--redact=100',
        '--no-banner', '--no-color', '--exit-code', '1', '--report-format', 'json',
        '--report-path', (Join-Path $directory 'report.json'), $repository)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $scanner @arguments 1> (Join-Path $directory 'stdout.log') 2> (Join-Path $directory 'stderr.log')
        return $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
}
try {
    Invoke-ProbeGit init --quiet --initial-branch=main
    Invoke-ProbeGit config user.name 'Scanner Test'
    Invoke-ProbeGit config user.email 'scanner@example.invalid'
    Invoke-ProbeGit commit --allow-empty --quiet -m 'Synthetic clean history'
    if ((Invoke-ProbeScan) -ne 0) { throw 'Clean history must pass.' }
    $token = 'ghp_' + [guid]::NewGuid().ToString('N') + 'A1b2'
    [IO.File]::WriteAllText((Join-Path $repository 'probe.txt'), "token=$token # gitleaks:allow")
    Invoke-ProbeGit add probe.txt
    Invoke-ProbeGit commit --quiet -m 'Synthetic scanner detection case'
    Invoke-ProbeGit rm --quiet probe.txt
    Invoke-ProbeGit commit --quiet -m 'Delete synthetic detection case'
    if ((Invoke-ProbeScan) -ne 1) { throw 'Deleted synthetic secret must fail the history scan.' }
    $report = Get-Content (Join-Path $directory 'report.json') -Raw
    $logs = (Get-Content (Join-Path $directory 'stdout.log') -Raw) + (Get-Content (Join-Path $directory 'stderr.log') -Raw)
    if ($report.Contains($token) -or $logs.Contains($token)) { throw 'Scanner redaction failed.' }
    $findings = @($report | ConvertFrom-Json)
    if ($findings.Count -lt 1) { throw 'Expected a synthetic secret finding.' }
    Write-Output 'Scanner regression passed: clean history, deleted secret, ignored allow comment and complete redaction.'
} finally {
    Remove-Item -Recurse -Force $directory
}
