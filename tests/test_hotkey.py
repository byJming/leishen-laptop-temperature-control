import unittest

from thunderobot_thermal.hotkey import DEFAULT_HOTKEY_TEXT, ManualFullHotkeyState


class ManualFullHotkeyStateTests(unittest.TestCase):
    def test_toggle_switches_manual_full_state(self) -> None:
        state = ManualFullHotkeyState()

        self.assertFalse(state.is_enabled())
        self.assertTrue(state.toggle())
        self.assertTrue(state.is_enabled())
        self.assertFalse(state.toggle())
        self.assertFalse(state.is_enabled())

    def test_initial_state_can_start_enabled(self) -> None:
        state = ManualFullHotkeyState(enabled=True)

        self.assertTrue(state.is_enabled())

    def test_hotkey_text_documents_selected_shortcut(self) -> None:
        self.assertEqual(DEFAULT_HOTKEY_TEXT, "Ctrl+Alt+Shift+0")
