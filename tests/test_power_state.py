import unittest

from thunderobot_thermal.power_state import effective_runtime_settings


class EffectiveRuntimeSettingsTests(unittest.TestCase):
    def test_uses_configured_settings_on_ac_power(self) -> None:
        settings = effective_runtime_settings("high", "aggressive", on_ac_power=True)

        self.assertEqual(settings.mode, "high")
        self.assertEqual(settings.profile, "aggressive")
        self.assertTrue(settings.on_ac_power)

    def test_uses_low_power_quiet_settings_on_battery(self) -> None:
        settings = effective_runtime_settings("high", "aggressive", on_ac_power=False)

        self.assertEqual(settings.mode, "office")
        self.assertEqual(settings.profile, "quiet")
        self.assertFalse(settings.on_ac_power)
