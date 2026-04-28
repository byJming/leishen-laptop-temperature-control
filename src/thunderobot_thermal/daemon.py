from __future__ import annotations

import argparse
import signal
import sys
import time

import psutil

from .fan_strategy import FanCommand, SensorSnapshot, ThermalPolicy
from .hotkey import DEFAULT_HOTKEY_TEXT, GlobalHotkeyListener, ManualFullHotkeyState
from .leishen_smi import LeishenSmiClient, activate_windows_power_plan
from .power_state import EffectiveRuntimeSettings, effective_runtime_settings, is_ac_power_connected
from .runtime_status import write_runtime_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="轻量温控守护进程")
    parser.add_argument("--interval", type=float, default=2.0, help="采样间隔，单位秒")
    parser.add_argument("--mode", choices=("high", "game", "office"), default="high", help="性能模式")
    parser.add_argument(
        "--profile",
        choices=("aggressive", "balanced", "quiet"),
        default="aggressive",
        help="温控策略",
    )
    parser.add_argument("--manual-full", action="store_true", help="强制三风扇满转")
    parser.add_argument("--once", action="store_true", help="只执行一次控制循环")
    parser.add_argument("--no-powercfg", action="store_true", help="不切换 Windows 电源计划")
    parser.add_argument("--no-hotkey", action="store_true", help="不注册全局满转快捷键")
    parser.add_argument("--allow-controlcenter", action="store_true", help="允许和原厂控制中心同时运行")
    parser.add_argument("--release-on-exit", action="store_true", help="退出时把风扇控制权交还给固件默认策略")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.allow_controlcenter:
        conflicting = find_control_center_processes()
        if conflicting:
            print(
                "检测到原厂控制中心正在运行，会和本守护进程争夺风扇控制："
                + ", ".join(conflicting)
                + "。请先退出原厂控制中心，或显式传入 --allow-controlcenter。",
                file=sys.stderr,
            )
            return 2

    client = LeishenSmiClient()
    stopped = False
    previous: FanCommand | None = None
    active_settings: EffectiveRuntimeSettings | None = None
    policy: ThermalPolicy | None = None
    manual_full_state = ManualFullHotkeyState(enabled=args.manual_full)
    hotkey_listener: GlobalHotkeyListener | None = None

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    if not args.no_hotkey and not args.once:
        hotkey_listener = GlobalHotkeyListener(manual_full_state)
        hotkey_listener.start()
        if hotkey_listener.error:
            print(f"{DEFAULT_HOTKEY_TEXT} 注册失败：{hotkey_listener.error}", file=sys.stderr, flush=True)
        else:
            print(f"{DEFAULT_HOTKEY_TEXT} 已注册：按一次开启满转，再按一次恢复策略。", flush=True)

    client.set_fan_control_enabled(True)

    try:
        while not stopped:
            settings = effective_runtime_settings(
                configured_mode=args.mode,
                configured_profile=args.profile,
                on_ac_power=is_ac_power_connected(),
            )
            if settings != active_settings:
                client.set_power_mode(settings.mode)
                if not args.no_powercfg:
                    activate_windows_power_plan(settings.mode)
                policy = ThermalPolicy.from_name(settings.profile)
                active_settings = settings

            snapshot = client.read_sensors()
            if policy is None:
                policy = ThermalPolicy.from_name(args.profile)
            manual_full = manual_full_state.is_enabled()
            command = select_command(policy, previous, snapshot, manual_full)
            client.set_fans(command)
            previous = command
            if active_settings is not None:
                write_runtime_status(
                    mode=active_settings.mode,
                    profile=active_settings.profile,
                    manual_full=manual_full,
                    on_ac_power=active_settings.on_ac_power,
                )

            print(
                "{0}/{1}{2} CPU {3}C/{4}RPM GPU {5}C/{6}RPM SYS {7}C/{8}RPM -> fan {9}/{10}/{11}%".format(
                    active_settings.mode if active_settings else args.mode,
                    active_settings.profile if active_settings else args.profile,
                    " manual-full" if manual_full else "",
                    snapshot.cpu_temp,
                    snapshot.cpu_fan_rpm,
                    snapshot.gpu_temp,
                    snapshot.gpu_fan_rpm,
                    snapshot.sys_temp,
                    snapshot.sys_fan_rpm,
                    command.cpu,
                    command.gpu,
                    command.sys,
                ),
                flush=True,
            )

            if args.once:
                break
            time.sleep(args.interval)
    finally:
        if hotkey_listener is not None:
            hotkey_listener.stop()
        if args.release_on_exit:
            client.release_fan_control()

    return 0


def find_control_center_processes() -> list[str]:
    names: list[str] = []
    for process in psutil.process_iter(("name", "pid")):
        try:
            name = process.info.get("name") or ""
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if name.lower() in {"controlcenter.exe", "controlcenterdaemon.exe"}:
            names.append(f"{name}:{process.info.get('pid')}")
    return names


def select_command(
    policy: ThermalPolicy,
    previous: FanCommand | None,
    snapshot: SensorSnapshot,
    manual_full: bool,
) -> FanCommand:
    target = policy.target_for(snapshot, manual_full=manual_full)
    if manual_full or target == FanCommand(policy.max_speed, policy.max_speed, policy.max_speed):
        return target
    return policy.next_command(previous, target)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

