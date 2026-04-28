param(
    [string] $ShortcutName = '雷神温控.lnk'
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = Split-Path -Parent $PSScriptRoot
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop $ShortcutName
$Launcher = Join-Path $Root 'scripts\run-gui.ps1'

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = 'pwsh.exe'
$Shortcut.Arguments = "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File `"$Launcher`""
$Shortcut.WorkingDirectory = $Root
$Shortcut.IconLocation = 'C:\Program Files (x86)\Leishen\ControlCenter\LeiShen.ico'
$Shortcut.Description = '雷神轻量温控控制面板'
$Shortcut.Save()

Write-Output "已创建桌面快捷方式：$ShortcutPath"
