from __future__ import annotations

import argparse
import signal
import sys
import time

import psutil

from .fan_strategy import FanCommand, ThermalPolicy
from .leishen_smi import LeishenSmiClient, activate_windows_power_plan


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
    policy = ThermalPolicy.from_name(args.profile)
    stopped = False
    previous: FanCommand | None = None

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    client.set_power_mode(args.mode)
    client.set_fan_control_enabled(True)
    if not args.no_powercfg:
        activate_windows_power_plan(args.mode)

    try:
        while not stopped:
            snapshot = client.read_sensors()
            target = policy.target_for(snapshot, manual_full=args.manual_full)
            command = policy.next_command(previous, target)
            client.set_fans(command)
            previous = command

            print(
                "CPU {0}C/{1}RPM GPU {2}C/{3}RPM SYS {4}C/{5}RPM -> fan {6}/{7}/{8}%".format(
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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

