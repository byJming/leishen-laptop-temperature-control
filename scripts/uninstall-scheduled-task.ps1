param(
    [string] $TaskName = 'ThunderobotThermalDaemon'
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Output "已删除计划任务：$TaskName"
