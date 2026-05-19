$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = $env:PYTHON
if (-not $Python) {
    $Python = "python"
}

Set-Location $Root
& $Python -m outpanel.app --host 127.0.0.1 --port 8000
