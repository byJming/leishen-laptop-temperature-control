from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

from .leishen_smi import LeishenSmiClient
from .manager import (
    RuntimeConfig,
    control_center_processes,
    install_scheduled_task,
    is_daemon_running,
    is_elevated,
    load_config,
    restart_daemon,
    save_config,
    scheduled_task_exists,
    start_daemon,
    stop_daemon,
    uninstall_scheduled_task,
)


MODE_LABELS = {"high": "高性能", "game": "游戏", "office": "办公"}
PROFILE_LABELS = {"aggressive": "激进", "balanced": "均衡", "quiet": "安静"}


class ThermalControlApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("雷神温控")
        self.geometry("820x620")
        self.minsize(820, 620)
        self.resizable(False, False)
        self.configure(bg="#101216")

        self.config_data = load_config()
        self.client: LeishenSmiClient | None = None
        self.is_running = False
        self.is_startup = False
        self.mode = self.config_data.mode
        self.profile = self.config_data.profile
        self.manual_full = self.config_data.manual_full
        self.status_refreshing = False
        self.sensor_refreshing = False
        self.operation_running = False
        self.busy_dots = 0

        self._build_layout()
        self.refresh_status()
        self.after(400, self.refresh_sensors)

    def _build_layout(self) -> None:
        self.main = tk.Frame(self, bg="#101216", padx=28, pady=24)
        self.main.pack(fill="both", expand=True)

        header = tk.Frame(self.main, bg="#101216")
        header.pack(fill="x", pady=(0, 18))
        tk.Label(header, text="雷神温控", bg="#101216", fg="#ffffff", font=("Microsoft YaHei UI", 24, "bold")).pack(side="left")
        self.admin_badge = tk.Label(
            header,
            text="权限检测中",
            bg="#1f2933",
            fg="#b9c4d0",
            padx=10,
            pady=4,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.admin_badge.pack(side="right", pady=(7, 0))
        self.busy_label = tk.Label(
            header,
            text="",
            bg="#101216",
            fg="#ffbd73",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.busy_label.pack(side="right", padx=(0, 12), pady=(7, 0))

        self.status_panel = self._panel()
        self.status_panel.pack(fill="x")
        self.status_label = self._label(self.status_panel, "正在读取状态", size=13, color="#ff9f43", bold=True)
        self.status_label.pack(anchor="w")
        self.sensor_label = self._label(self.status_panel, "传感器：等待刷新", size=11)
        self.sensor_label.pack(anchor="w", pady=(14, 0))
        self.conflict_label = self._label(self.status_panel, "", size=10, color="#9aa5b4")
        self.conflict_label.pack(anchor="w", pady=(8, 0))

        self.controls_panel = self._panel()
        self.controls_panel.pack(fill="both", expand=True, pady=(16, 0))
        self.controls_panel.pack_propagate(False)
        self.controls_panel.configure(height=300)

        top = tk.Frame(self.controls_panel, bg="#1a1f26")
        top.pack(fill="x")
        self.run_button = self._button(top, "启动后台", self.toggle_daemon, accent=True)
        self.run_button.pack(side="left")
        self.startup_button = self._button(top, "开启自启动", self.toggle_startup)
        self.startup_button.pack(side="left", padx=10)
        self.full_button = self._button(top, "手动满转：关", self.toggle_manual_full)
        self.full_button.pack(side="left", padx=10)
        self.release_button = self._button(top, "停止并交还默认", self.stop_and_release)
        self.release_button.pack(side="right")

        sections = tk.Frame(self.controls_panel, bg="#1a1f26")
        sections.pack(fill="x", pady=(22, 0))

        mode_box = tk.Frame(sections, bg="#1a1f26")
        mode_box.pack(side="left", fill="x", expand=True)
        self._label(mode_box, "性能模式", size=10, color="#9aa5b4").pack(anchor="w", pady=(0, 8))
        self.mode_buttons = self._segmented(mode_box, MODE_LABELS, self.set_mode)

        profile_box = tk.Frame(sections, bg="#1a1f26")
        profile_box.pack(side="left", fill="x", expand=True, padx=(24, 0))
        self._label(profile_box, "温控策略", size=10, color="#9aa5b4").pack(anchor="w", pady=(0, 8))
        self.profile_buttons = self._segmented(profile_box, PROFILE_LABELS, self.set_profile)

        bottom = tk.Frame(self.main, bg="#101216")
        bottom.pack(fill="x", pady=(4, 0))
        self.apply_button = self._button(bottom, "应用当前设置", self.apply_settings, accent=True)
        self.apply_button.pack(side="left")
        self.refresh_button = self._button(bottom, "刷新状态", self.refresh_status)
        self.refresh_button.pack(side="right")

        self.update_button_states()

    def _panel(self) -> tk.Frame:
        return tk.Frame(self.main, bg="#191e25", padx=20, pady=18, highlightthickness=1, highlightbackground="#28313d")

    def _label(self, parent: tk.Misc, text: str, size: int = 10, color: str = "#e7edf5", bold: bool = False) -> tk.Label:
        weight = "bold" if bold else "normal"
        return tk.Label(parent, text=text, bg=parent["bg"], fg=color, font=("Microsoft YaHei UI", size, weight), anchor="w", justify="left")

    def _button(self, parent: tk.Misc, text: str, command, accent: bool = False) -> tk.Button:
        bg = "#ff7a1a" if accent else "#222a35"
        fg = "#151515" if accent else "#e7edf5"
        active_bg = "#ff9a3d" if accent else "#2d3745"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            font=("Microsoft YaHei UI", 10, "bold" if accent else "normal"),
            cursor="hand2",
        )

    def _segmented(self, parent: tk.Misc, labels: dict[str, str], command) -> dict[str, tk.Button]:
        frame = tk.Frame(parent, bg="#27313d")
        frame.pack(anchor="w")
        buttons: dict[str, tk.Button] = {}
        for key, label in labels.items():
            button = self._button(frame, label, lambda value=key: command(value))
            button.pack(side="left", padx=1, pady=1)
            buttons[key] = button
        return buttons

    def current_config(self) -> RuntimeConfig:
        return RuntimeConfig(mode=self.mode, profile=self.profile, interval=2.0, manual_full=self.manual_full)

    def set_busy(self, busy: bool) -> None:
        self.operation_running = busy
        self.configure(cursor="watch" if busy else "")
        self.apply_button.configure(text="应用中..." if busy else "应用当前设置")
        self.update_idletasks()
        if busy:
            self.animate_busy()
        else:
            self.busy_label.configure(text="")

    def animate_busy(self) -> None:
        if not self.operation_running:
            return
        self.busy_dots = (self.busy_dots + 1) % 4
        self.busy_label.configure(text="正在应用设置" + "." * self.busy_dots)
        self.after(300, self.animate_busy)

    def update_button_states(self) -> None:
        self.run_button.configure(text="停止后台" if self.is_running else "启动后台")
        self.startup_button.configure(text="关闭自启动" if self.is_startup else "开启自启动")
        self.full_button.configure(text="手动满转：开" if self.manual_full else "手动满转：关")

        for key, button in self.mode_buttons.items():
            self._paint_segment(button, key == self.mode)
        for key, button in self.profile_buttons.items():
            self._paint_segment(button, key == self.profile)

    def _paint_segment(self, button: tk.Button, selected: bool) -> None:
        if selected:
            button.configure(bg="#ff7a1a", fg="#151515", activebackground="#ff9a3d", activeforeground="#151515")
        else:
            button.configure(bg="#222a35", fg="#d7dde6", activebackground="#2d3745", activeforeground="#ffffff")

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update_button_states()
        self.apply_settings()

    def set_profile(self, profile: str) -> None:
        self.profile = profile
        self.update_button_states()
        self.apply_settings()

    def toggle_manual_full(self) -> None:
        self.manual_full = not self.manual_full
        self.update_button_states()
        self.apply_settings()

    def toggle_daemon(self) -> None:
        if self.operation_running:
            return
        config = self.current_config()
        if not self.is_running:
            conflicts = control_center_processes()
            if conflicts:
                messagebox.showwarning("无法启动", "请先退出原厂控制中心，避免争夺风扇控制。")
                self.refresh_status()
                return
            self.run_background(lambda: start_daemon(config))
        else:
            self.run_background(lambda: stop_daemon(release=True))

    def toggle_startup(self) -> None:
        if self.operation_running:
            return
        config = self.current_config()
        if not self.is_startup:
            self.run_background(lambda: install_scheduled_task(config))
        else:
            self.run_background(uninstall_scheduled_task)

    def apply_settings(self) -> None:
        if self.operation_running:
            return
        config = self.current_config()
        save_config(config)
        self.run_background(lambda: self._apply_settings_background(config))

    def _apply_settings_background(self, config: RuntimeConfig) -> None:
        restart_daemon(config)
        if self.is_startup:
            install_scheduled_task(config)

    def stop_and_release(self) -> None:
        if self.operation_running:
            return
        self.run_background(lambda: stop_daemon(release=True))

    def run_background(self, action) -> None:
        def worker() -> None:
            self.after(0, lambda: self.set_busy(True))
            try:
                action()
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                self.after(0, lambda: messagebox.showerror("操作失败", error))
            finally:
                self.after(0, self.refresh_status)
                self.after(0, lambda: self.set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_status(self) -> None:
        if self.status_refreshing:
            return
        self.status_refreshing = True
        threading.Thread(target=self._refresh_status_background, daemon=True).start()

    def _refresh_status_background(self) -> None:
        try:
            running = is_daemon_running()
            startup = scheduled_task_exists()
            conflicts = control_center_processes()
            elevated = is_elevated()
            self.after(0, lambda: self._apply_status(running, startup, conflicts, elevated))
        finally:
            self.after(0, lambda: setattr(self, "status_refreshing", False))

    def _apply_status(self, running: bool, startup: bool, conflicts: list[str], elevated: bool) -> None:
        self.is_running = running
        self.is_startup = startup
        admin_text = "管理员" if elevated else "非管理员"
        self.status_label.configure(text=f"后台：{'运行中' if running else '未运行'}    自启动：{'已开启' if startup else '未开启'}")
        self.admin_badge.configure(
            text=admin_text,
            bg="#173d2c" if elevated else "#4a2f18",
            fg="#88f0bc" if elevated else "#ffbd73",
        )
        self.conflict_label.configure(text="原厂控制中心：" + ("未运行" if not conflicts else "运行中，建议退出"))
        self.update_button_states()

    def refresh_sensors(self) -> None:
        if not self.sensor_refreshing:
            self.sensor_refreshing = True
            threading.Thread(target=self._read_sensors_background, daemon=True).start()
        self.after(3000, self.refresh_sensors)

    def _read_sensors_background(self) -> None:
        try:
            if self.client is None:
                self.client = LeishenSmiClient(persistent=False)
            snapshot = self.client.read_sensors()
            text = "CPU {0}°C / {1} RPM    GPU {2}°C / {3} RPM    SYS {4}°C / {5} RPM".format(
                snapshot.cpu_temp,
                snapshot.cpu_fan_rpm,
                snapshot.gpu_temp,
                snapshot.gpu_fan_rpm,
                snapshot.sys_temp,
                snapshot.sys_fan_rpm,
            )
            self.after(0, lambda: self.sensor_label.configure(text=text))
        except Exception as exc:  # noqa: BLE001
            self.client = None
            error = str(exc)
            if "RW_GMWMI" in error or "winmgmts" in error:
                error = "无法访问风扇 WMI 接口。请用管理员权限启动，并确认 ControlCenter 驱动存在。"
            self.after(0, lambda: self.sensor_label.configure(text=f"传感器读取失败：{error}"))
        finally:
            self.after(0, lambda: setattr(self, "sensor_refreshing", False))
            self.refresh_status()


def main() -> int:
    app = ThermalControlApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
