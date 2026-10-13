param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
$ErrorActionPreference = 'Stop'
& uv run --locked python (Join-Path $PSScriptRoot 'git_delivery.py') @Arguments
exit $LASTEXITCODE
