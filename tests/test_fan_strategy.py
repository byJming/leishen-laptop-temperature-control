import unittest

from thunderobot_thermal.fan_strategy import FanCommand, FanCurve, SensorSnapshot, ThermalPolicy


class FanCurveTests(unittest.TestCase):
    def test_interpolates_between_points(self) -> None:
        curve = FanCurve(((50, 40), (70, 80)))

        self.assertEqual(curve.speed_for(60), 60)

    def test_clamps_below_and_above_curve(self) -> None:
        curve = FanCurve(((50, 40), (70, 80)))

        self.assertEqual(curve.speed_for(30), 40)
        self.assertEqual(curve.speed_for(90), 80)


class ThermalPolicyTests(unittest.TestCase):
    def test_aggressive_policy_reaches_full_speed_before_throttle(self) -> None:
        policy = ThermalPolicy.aggressive()

        command = policy.target_for(SensorSnapshot(cpu_temp=92, gpu_temp=70, sys_temp=60))

        self.assertEqual(command.cpu, 100)
        self.assertEqual(command.sys, 100)

    def test_emergency_forces_full_speed(self) -> None:
        policy = ThermalPolicy.aggressive()

        command = policy.target_for(SensorSnapshot(cpu_temp=95, gpu_temp=40, sys_temp=40))

        self.assertEqual(command, FanCommand(100, 100, 100))

    def test_manual_full_forces_full_speed(self) -> None:
        policy = ThermalPolicy.aggressive()

        command = policy.target_for(SensorSnapshot(cpu_temp=45, gpu_temp=45, sys_temp=40), manual_full=True)

        self.assertEqual(command, FanCommand(100, 100, 100))

    def test_profiles_have_different_midrange_behavior(self) -> None:
        snapshot = SensorSnapshot(cpu_temp=75, gpu_temp=75, sys_temp=55)

        quiet = ThermalPolicy.from_name("quiet").target_for(snapshot)
        aggressive = ThermalPolicy.from_name("aggressive").target_for(snapshot)

        self.assertLess(quiet.cpu, aggressive.cpu)
        self.assertLess(quiet.gpu, aggressive.gpu)

    def test_cpu_heat_boosts_gpu_side_fan_for_chassis_exchange(self) -> None:
        policy = ThermalPolicy.aggressive()

        command = policy.target_for(SensorSnapshot(cpu_temp=88, gpu_temp=49, sys_temp=45))

        self.assertGreaterEqual(command.cpu, 95)
        self.assertGreaterEqual(command.gpu, 85)
        self.assertGreaterEqual(command.sys, 95)

    def test_ramp_increases_quickly_and_decreases_slowly(self) -> None:
        policy = ThermalPolicy.aggressive()

        self.assertEqual(
            policy.next_command(FanCommand(40, 40, 40), FanCommand(90, 70, 50)),
            FanCommand(60, 60, 50),
        )
        self.assertEqual(
            policy.next_command(FanCommand(80, 80, 80), FanCommand(40, 40, 40)),
            FanCommand(75, 75, 75),
        )


if __name__ == "__main__":
    unittest.main()

