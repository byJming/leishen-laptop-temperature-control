param(
    [string] $TaskName = 'ThunderobotThermalDaemon',
    [string] $Mode = 'high',
    [ValidateSet('aggressive', 'balanced', 'quiet')]
    [string] $Profile = 'aggressive',
    [double] $Interval = 2.0
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $Root 'scripts\run-daemon.ps1'
$Arguments = "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$Script`" --mode $Mode --profile $Profile --interval $Interval"

$Action = New-ScheduledTaskAction -Execute 'pwsh.exe' -Argument $Arguments -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$PrincipalUser = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
$Principal = New-ScheduledTaskPrincipal -UserId $PrincipalUser -LogonType Interactive -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
Write-Output "已创建计划任务：$TaskName"
