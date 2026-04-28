param(
    [string] $PythonPath = 'python',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $DaemonArgs
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $Root 'src'
& $PythonPath -m thunderobot_thermal.daemon @DaemonArgs
