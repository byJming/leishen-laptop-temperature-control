from __future__ import annotations

import ctypes
from dataclasses import dataclass


AC_LINE_OFFLINE = 0
AC_LINE_ONLINE = 1


@dataclass(frozen=True)
class EffectiveRuntimeSettings:
    mode: str
    profile: str
    on_ac_power: bool


class SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ac_line_status", ctypes.c_ubyte),
        ("battery_flag", ctypes.c_ubyte),
        ("battery_life_percent", ctypes.c_ubyte),
        ("system_status_flag", ctypes.c_ubyte),
        ("battery_life_time", ctypes.c_ulong),
        ("battery_full_life_time", ctypes.c_ulong),
    ]


def is_ac_power_connected() -> bool:
    status = SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return True
    if status.ac_line_status == AC_LINE_ONLINE:
        return True
    if status.ac_line_status == AC_LINE_OFFLINE:
        return False
    return True


def effective_runtime_settings(configured_mode: str, configured_profile: str, on_ac_power: bool) -> EffectiveRuntimeSettings:
    if on_ac_power:
        return EffectiveRuntimeSettings(mode=configured_mode, profile=configured_profile, on_ac_power=True)
    return EffectiveRuntimeSettings(mode="office", profile="quiet", on_ac_power=False)
