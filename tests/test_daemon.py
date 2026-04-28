import unittest

from thunderobot_thermal.daemon import select_command
from thunderobot_thermal.fan_strategy import FanCommand, SensorSnapshot, ThermalPolicy


class SelectCommandTests(unittest.TestCase):
    def test_manual_full_bypasses_ramp_limit(self) -> None:
        policy = ThermalPolicy.aggressive()

        command = select_command(
            policy,
            previous=FanCommand(30, 30, 30),
            snapshot=SensorSnapshot(cpu_temp=50, gpu_temp=40, sys_temp=40),
            manual_full=True,
        )

        self.assertEqual(command, FanCommand(100, 100, 100))

    def test_emergency_bypasses_ramp_limit(self) -> None:
        policy = ThermalPolicy.aggressive()

        command = select_command(
            policy,
            previous=FanCommand(30, 30, 30),
            snapshot=SensorSnapshot(cpu_temp=96, gpu_temp=40, sys_temp=40),
            manual_full=False,
        )

        self.assertEqual(command, FanCommand(100, 100, 100))

    def test_normal_policy_still_uses_ramp_limit(self) -> None:
        policy = ThermalPolicy.aggressive()

        command = select_command(
            policy,
            previous=FanCommand(30, 30, 30),
            snapshot=SensorSnapshot(cpu_temp=88, gpu_temp=40, sys_temp=40),
            manual_full=False,
        )

        self.assertEqual(command, FanCommand(50, 50, 50))


if __name__ == "__main__":
    unittest.main()
