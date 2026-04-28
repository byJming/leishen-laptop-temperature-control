import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import thunderobot_thermal.runtime_status as runtime_status
from thunderobot_thermal.runtime_status import read_runtime_status, write_runtime_status


class RuntimeStatusTests(unittest.TestCase):
    def test_round_trips_runtime_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status_path = Path(directory) / "runtime_status.json"
            with patch.object(runtime_status, "STATE_DIR", Path(directory)), patch.object(
                runtime_status, "RUNTIME_STATUS_PATH", status_path
            ):
                write_runtime_status("high", "aggressive", manual_full=True, on_ac_power=True)

                status = read_runtime_status()

        self.assertIsNotNone(status)
        assert status is not None
        self.assertEqual(status.mode, "high")
        self.assertEqual(status.profile, "aggressive")
        self.assertTrue(status.manual_full)
        self.assertTrue(status.on_ac_power)

    def test_ignores_stale_runtime_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            status_path = Path(directory) / "runtime_status.json"
            with patch.object(runtime_status, "STATE_DIR", Path(directory)), patch.object(
                runtime_status, "RUNTIME_STATUS_PATH", status_path
            ), patch("thunderobot_thermal.runtime_status.time.time", return_value=1000.0):
                write_runtime_status("high", "aggressive", manual_full=False, on_ac_power=True)

            with patch.object(runtime_status, "RUNTIME_STATUS_PATH", status_path), patch(
                "thunderobot_thermal.runtime_status.time.time",
                return_value=1020.0,
            ):
                status = read_runtime_status(max_age_seconds=10)

        self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
