from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_ROOT / "state"
CONFIG_PATH = STATE_DIR / "config.json"
LOG_PATH = STATE_DIR / "daemon.log"
TASK_NAME = "ThunderobotThermalDaemon"


@dataclass(frozen=True)
class RuntimeConfig:
    mode: str = "high"
    profile: str = "aggressive"
    interval: float = 2.0
    manual_full: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeConfig":
        return cls(
            mode=str(data.get("mode", cls.mode)),
            profile=str(data.get("profile", cls.profile)),
            interval=float(data.get("interval", cls.interval)),
            manual_full=bool(data.get("manual_full", cls.manual_full)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "profile": self.profile,
            "interval": self.interval,
            "manual_full": self.manual_full,
        }


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> RuntimeConfig:
    ensure_state_dir()
    if not CONFIG_PATH.exists():
        config = RuntimeConfig()
        save_config(config)
        return config
    return RuntimeConfig.from_dict(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))


def save_config(config: RuntimeConfig) -> None:
    ensure_state_dir()
    CONFIG_PATH.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def python_console_executable() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        candidate = executable.with_name("python.exe")
        if candidate.exists():
            return str(candidate)
    return str(executable)


def daemon_processes() -> list[psutil.Process]:
    processes: list[psutil.Process] = []
    for process in psutil.process_iter(("pid", "name", "cmdline")):
        try:
            cmdline = process.info.get("cmdline") or []
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        joined = " ".join(cmdline).lower()
        if "thunderobot_thermal.daemon" in joined:
            processes.append(process)
    return processes


def control_center_processes() -> list[str]:
    names: list[str] = []
    for process in psutil.process_iter(("pid", "name")):
        try:
            name = process.info.get("name") or ""
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if name.lower() in {"controlcenter.exe", "controlcenterdaemon.exe"}:
            names.append(f"{name}:{process.info.get('pid')}")
    return names


def is_elevated() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_daemon_running() -> bool:
    return bool(daemon_processes())


def start_daemon(config: RuntimeConfig) -> None:
    if is_daemon_running():
        return

    ensure_state_dir()
    save_config(config)
    command = [
        python_console_executable(),
        "-m",
        "thunderobot_thermal.daemon",
        "--mode",
        config.mode,
        "--profile",
        config.profile,
        "--interval",
        str(config.interval),
    ]
    if config.manual_full:
        command.append("--manual-full")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    log = LOG_PATH.open("a", encoding="utf-8")
    subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def stop_daemon(release: bool = True) -> None:
    for process in daemon_processes():
        try:
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    deadline = time.time() + 5
    for process in daemon_processes():
        remaining = max(0.1, deadline - time.time())
        try:
            process.wait(timeout=remaining)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            try:
                process.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    if release:
        release_fan_control_once()


def release_fan_control_once() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    code = (
        "from thunderobot_thermal.leishen_smi import LeishenSmiClient;"
        "LeishenSmiClient().release_fan_control()"
    )
    subprocess.run(
        [python_console_executable(), "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )


def restart_daemon(config: RuntimeConfig) -> None:
    was_running = is_daemon_running()
    save_config(config)
    if was_running:
        stop_daemon(release=False)
        start_daemon(config)


def scheduled_task_exists() -> bool:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", TASK_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    return result.returncode == 0


def install_scheduled_task(config: RuntimeConfig) -> None:
    save_config(config)
    script = PROJECT_ROOT / "scripts" / "install-scheduled-task.ps1"
    result = subprocess.run(
        [
            "pwsh.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-TaskName",
            TASK_NAME,
            "-Mode",
            config.mode,
            "-Profile",
            config.profile,
            "-Interval",
            str(config.interval),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stdout + result.stderr).strip() or "创建计划任务失败")


def uninstall_scheduled_task() -> None:
    if not scheduled_task_exists():
        return
    script = PROJECT_ROOT / "scripts" / "uninstall-scheduled-task.ps1"
    result = subprocess.run(
        [
            "pwsh.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-TaskName",
            TASK_NAME,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stdout + result.stderr).strip() or "删除计划任务失败")

