from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FanCommand:
    cpu: int
    gpu: int
    sys: int

    def clamped(self, minimum: int = 30, maximum: int = 100) -> "FanCommand":
        return FanCommand(
            cpu=_clamp(self.cpu, minimum, maximum),
            gpu=_clamp(self.gpu, minimum, maximum),
            sys=_clamp(self.sys, minimum, maximum),
        )


@dataclass(frozen=True)
class SensorSnapshot:
    cpu_temp: int
    gpu_temp: int
    sys_temp: int
    cpu_fan_rpm: int = 0
    gpu_fan_rpm: int = 0
    sys_fan_rpm: int = 0


class FanCurve:
    def __init__(self, points: Iterable[tuple[int, int]]) -> None:
        sorted_points = sorted(points)
        if len(sorted_points) < 2:
            raise ValueError("fan curve requires at least two points")
        if any(speed < 0 or speed > 100 for _, speed in sorted_points):
            raise ValueError("fan speed must be between 0 and 100")
        self._points = tuple(sorted_points)

    def speed_for(self, temperature: int) -> int:
        if temperature <= self._points[0][0]:
            return self._points[0][1]
        if temperature >= self._points[-1][0]:
            return self._points[-1][1]

        for (left_temp, left_speed), (right_temp, right_speed) in zip(self._points, self._points[1:]):
            if left_temp <= temperature <= right_temp:
                span = right_temp - left_temp
                ratio = (temperature - left_temp) / span
                return round(left_speed + ((right_speed - left_speed) * ratio))

        return self._points[-1][1]


@dataclass(frozen=True)
class ThermalPolicy:
    cpu_curve: FanCurve
    gpu_curve: FanCurve
    sys_curve: FanCurve
    min_speed: int = 30
    max_speed: int = 100
    emergency_cpu_temp: int = 95
    emergency_gpu_temp: int = 86
    emergency_sys_temp: int = 80
    up_step: int = 20
    down_step: int = 5
    cross_cooling_offset: int = 10

    @staticmethod
    def aggressive() -> "ThermalPolicy":
        main_curve = FanCurve(
            (
                (45, 35),
                (55, 40),
                (65, 55),
                (75, 72),
                (82, 85),
                (88, 95),
                (92, 100),
            )
        )
        sys_curve = FanCurve(
            (
                (40, 40),
                (50, 50),
                (60, 68),
                (70, 85),
                (78, 100),
            )
        )
        return ThermalPolicy(cpu_curve=main_curve, gpu_curve=main_curve, sys_curve=sys_curve)

    @staticmethod
    def balanced() -> "ThermalPolicy":
        main_curve = FanCurve(
            (
                (45, 30),
                (55, 35),
                (65, 48),
                (75, 65),
                (82, 78),
                (88, 90),
                (93, 100),
            )
        )
        sys_curve = FanCurve(
            (
                (40, 35),
                (50, 42),
                (60, 58),
                (70, 78),
                (82, 100),
            )
        )
        return ThermalPolicy(cpu_curve=main_curve, gpu_curve=main_curve, sys_curve=sys_curve)

    @staticmethod
    def quiet() -> "ThermalPolicy":
        main_curve = FanCurve(
            (
                (45, 30),
                (58, 32),
                (68, 42),
                (78, 60),
                (85, 82),
                (92, 100),
            )
        )
        sys_curve = FanCurve(
            (
                (40, 30),
                (55, 36),
                (68, 60),
                (80, 100),
            )
        )
        return ThermalPolicy(cpu_curve=main_curve, gpu_curve=main_curve, sys_curve=sys_curve)

    @staticmethod
    def from_name(name: str) -> "ThermalPolicy":
        policies = {
            "aggressive": ThermalPolicy.aggressive,
            "balanced": ThermalPolicy.balanced,
            "quiet": ThermalPolicy.quiet,
        }
        try:
            return policies[name]()
        except KeyError as exc:
            raise ValueError(f"unsupported thermal profile: {name}") from exc

    def target_for(self, snapshot: SensorSnapshot, manual_full: bool = False) -> FanCommand:
        if manual_full or self._is_emergency(snapshot):
            return FanCommand(self.max_speed, self.max_speed, self.max_speed)

        cpu_speed = self.cpu_curve.speed_for(snapshot.cpu_temp)
        gpu_speed = self.gpu_curve.speed_for(snapshot.gpu_temp)
        cpu_speed = max(cpu_speed, gpu_speed - self.cross_cooling_offset)
        gpu_speed = max(gpu_speed, cpu_speed - self.cross_cooling_offset)
        sys_speed = max(
            self.sys_curve.speed_for(snapshot.sys_temp),
            cpu_speed,
            gpu_speed,
        )
        return FanCommand(cpu_speed, gpu_speed, sys_speed).clamped(self.min_speed, self.max_speed)

    def next_command(self, previous: FanCommand | None, target: FanCommand) -> FanCommand:
        if previous is None:
            return target.clamped(self.min_speed, self.max_speed)

        return FanCommand(
            cpu=self._ramp(previous.cpu, target.cpu),
            gpu=self._ramp(previous.gpu, target.gpu),
            sys=self._ramp(previous.sys, target.sys),
        ).clamped(self.min_speed, self.max_speed)

    def _is_emergency(self, snapshot: SensorSnapshot) -> bool:
        return (
            snapshot.cpu_temp >= self.emergency_cpu_temp
            or snapshot.gpu_temp >= self.emergency_gpu_temp
            or snapshot.sys_temp >= self.emergency_sys_temp
        )

    def _ramp(self, current: int, target: int) -> int:
        if target > current:
            return min(current + self.up_step, target)
        if target < current:
            return max(current - self.down_step, target)
        return current


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))

