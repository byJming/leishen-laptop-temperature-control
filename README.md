# 雷神笔记本轻量温控

这是一个面向雷神 / Thunderobot 部分笔记本的非官方轻量温控工具。它通过原厂 Control Center 已安装的 WMI/SMI 通道读取温度和风扇状态，并用独立守护进程接管风扇策略。

项目目标是替代原厂控制中心里较重、启动慢、默认风扇策略偏保守的温控部分。键盘灯、灯效等功能仍可在需要时临时打开原厂控制中心处理。

## 功能

- 图形界面操作，不需要日常输入命令。
- 后台静默运行温控守护进程。
- 支持开机自启动。
- 支持高性能、游戏、办公性能模式。
- 支持激进、均衡、安静温控策略。
- 拔掉电源后自动切换到低功耗和更保守风扇策略，重新插电后恢复原设置。
- 保留手动满转风扇功能。
- 后台运行时支持 `Ctrl+Alt+Shift+0` 切换手动满转，再按一次恢复自动温控。
- 支持停止接管并交还原厂默认控制。
- 针对多风口机型做了交叉助推：CPU 高温时也会适当提高 GPU / 右侧风扇转速，改善整机换热。

## 适用范围

目前仅在带有原厂 Control Center 驱动、并暴露 `root\wmi:RW_GMWMI` 接口的雷神笔记本上验证。不同批次、不同模具、不同 BIOS / EC 版本可能存在差异。

如果你的机器没有这个 WMI 类，程序会无法读取传感器，也不会正常控制风扇。

## 安装准备

需要 Windows、PowerShell 7、Python 3，以及原厂 Control Center 已安装过的底层驱动。

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

创建桌面快捷方式：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\create-desktop-shortcut.ps1
```

脚本会在当前用户桌面创建 `雷神温控.lnk`。以后直接双击这个快捷方式即可打开图形界面。

## 使用方式

首次打开快捷方式时，Windows 会弹出 UAC 管理员权限确认。风扇 WMI 接口和开机自启动计划任务都需要管理员权限。

图形界面里常用操作：

- `启动后台`：启动温控守护进程。
- `开启自启动`：创建登录后自动运行的计划任务。
- `手动满转`：临时将风扇拉满。
- `停止并交还默认`：停止守护进程，并把风扇控制交还给原厂默认策略。
- `性能模式`：切换高性能、游戏、办公模式。
- `温控策略`：切换激进、均衡、安静风扇策略。

建议日常保持原厂 Control Center 退出状态，避免两个程序同时写入风扇控制。

开启自启动后，程序会创建登录触发的计划任务，并记录当前 PowerShell 和 Python 的绝对路径，避免重启后因为系统 PATH 不一致导致后台无法启动。

后台守护进程运行时，可以按 `Ctrl+Alt+Shift+0` 切换手动满转。这个快捷键由本项目注册，独立于原厂 `Fn+1` OSD；如果原厂热键只显示图标但不改变实际转速，请使用这个快捷键或窗口里的 `手动满转`。

## 安全软件误报

部分安全软件可能会把本项目误报为可疑程序，原因通常是：

- 快捷方式会启动 PowerShell 脚本。
- 程序会请求管理员权限。
- 程序会创建 Windows 计划任务用于开机自启动。
- 程序会访问厂商 WMI 接口并控制风扇。

这些行为对温控工具来说是必要的，但也容易触发安全软件的启发式规则。建议从源码仓库自行检查脚本内容后运行。如果确认来源可信，可以在安全软件中对项目目录或桌面快捷方式加入信任。

## 温控策略

默认建议使用 `高性能 + 激进`。激进策略曲线如下：

```text
45°C 35%
55°C 40%
65°C 55%
72°C 72%
78°C 85%
84°C 95%
88°C 100%
```

保护逻辑：

- CPU >= 92°C 时三风扇直接 100%。
- GPU >= 86°C 时三风扇直接 100%。
- SYS >= 80°C 时三风扇直接 100%。
- 升速较快，降速较慢；进入 95% 以上高温目标时会绕过斜坡直接下发目标转速，减少 95-100°C 峰值停留。
- CPU 或 GPU 单侧高温时，另一个风扇也会参与排热，提高整机热交换效率。
- 使用电池供电时会临时使用 `办公 + 安静`，插回电源后自动恢复用户选择的性能模式和温控策略。

## 命令行用法

只运行一轮读取和控制：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-daemon.ps1 --once --no-powercfg
```

常驻运行：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-daemon.ps1 --mode high --profile aggressive --interval 2
```

手动满转：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-daemon.ps1 --manual-full
```

## 已知限制

- 这是非官方工具，不修改 BIOS、不刷 EC、不替换原厂文件。
- 依赖原厂安装的底层驱动和 WMI 接口。
- 不负责键盘灯、灯效、屏幕模式等原厂控制中心的其他功能。
- 开启自启动会创建名为 `ThunderobotThermalDaemon` 的 Windows 计划任务。
- 不同机型的风扇编号、风道结构和功耗策略可能不同，使用前建议先观察温度和转速是否符合预期。

## 开发与测试

运行单元测试：

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m unittest discover -s tests -v
```

## 免责声明

本项目按现状提供。风扇、温度、电源策略都属于硬件相关控制，使用者需要自行承担使用风险。请确保散热器、风扇、硅脂、进出风口和电源适配器状态正常，不要把软件温控当作硬件维护的替代品。

## License

MIT License
