"""
Tests unitaires pour SkillKorp K20 Ultimate (k20_driver.py, profile_manager.py, k20ctl).
Couvre les commandes HID, encodages de rapports, gestion des profils et CLI.
"""

import sys
import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch, mock_open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import k20_driver
from k20_driver import (
    POLLING_RATE_MAP,
    LIGHT_MODES,
    SIDE_LIGHT_MODES,
    REMAP_ACTIONS,
    KEY_LAYOUT,
    SkillkorpK20Driver,
    _HIDIOCSFEATURE,
    _HIDIOCGFEATURE,
    CMD_SET_REPORT,
    CMD_SET_PROFILE,
    CMD_SET_LEDPARAM,
    CMD_SET_KBOPTION,
    CMD_SET_SLEDPARAM,
    CMD_SET_RESERT,
    CMD_SET_DEBOUNCE,
    CMD_SET_SLEEPTIME,
    CMD_SET_KEYMATRIX_SIMPLE,
    CMD_SET_FN_SIMPLE,
    CMD_GET_BATTERY,
    CMD_SET_SLEEPTIME,
)
from profile_manager import ProfileManager, DEFAULT_PROFILES


class TestHidiocsMacro(unittest.TestCase):
    """Tests du calcul des ioctl macros HIDIOCSFEATURE et HIDIOCGFEATURE."""

    def test_hidiocsfeature_65bytes(self):
        result = _HIDIOCSFEATURE(65)
        self.assertIsInstance(result, int)
        expected = (3 << 30) | (65 << 16) | (ord('H') << 8) | 0x06
        self.assertEqual(result, expected)

    def test_hidiocgfeature_65bytes(self):
        result = _HIDIOCGFEATURE(65)
        self.assertIsInstance(result, int)
        expected = (3 << 30) | (65 << 16) | (ord('H') << 8) | 0x07
        self.assertEqual(result, expected)


class TestConstants(unittest.TestCase):
    """Tests des dictionnaires et constantes du protocole."""

    def test_polling_rate_map(self):
        self.assertIn(1000, POLLING_RATE_MAP)
        self.assertIn(500, POLLING_RATE_MAP)
        self.assertIn(250, POLLING_RATE_MAP)
        self.assertIn(125, POLLING_RATE_MAP)
        self.assertEqual(POLLING_RATE_MAP[1000], 1)
        self.assertEqual(POLLING_RATE_MAP[500], 2)
        self.assertEqual(POLLING_RATE_MAP[250], 4)
        self.assertEqual(POLLING_RATE_MAP[125], 8)

    def test_light_modes(self):
        mode_keys = [k for k, _, _ in LIGHT_MODES]
        self.assertIn("off", mode_keys)
        self.assertIn("wave", mode_keys)
        self.assertIn("breathing", mode_keys)
        self.assertIn("static", mode_keys)
        self.assertEqual(len(LIGHT_MODES), 10)

    def test_key_layout(self):
        self.assertEqual(len(KEY_LAYOUT), 85)
        names = [k["name"] for k in KEY_LAYOUT]
        self.assertIn("Esc", names)
        self.assertIn("A", names)
        self.assertIn("Z", names)
        self.assertIn("Espace", names)
        self.assertIn("Entrée", names)

    def test_remap_actions(self):
        self.assertIn("media_vol_up", REMAP_ACTIONS)
        self.assertIn("mouse_left", REMAP_ACTIONS)
        self.assertIn("copy", REMAP_ACTIONS)
        self.assertIn("disabled", REMAP_ACTIONS)
        for act, (label, payload) in REMAP_ACTIONS.items():
            self.assertEqual(len(payload), 4)


class TestDriverMethods(unittest.TestCase):
    """Tests des méthodes matérielles du pilote avec mock d'ioctl."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_config_dir = k20_driver.CONFIG_DIR
        self.orig_profile_file = k20_driver.DEFAULT_PROFILE_FILE
        k20_driver.CONFIG_DIR = self.temp_dir.name
        k20_driver.DEFAULT_PROFILE_FILE = os.path.join(self.temp_dir.name, "default_profile.json")

    def tearDown(self):
        k20_driver.CONFIG_DIR = self.orig_config_dir
        k20_driver.DEFAULT_PROFILE_FILE = self.orig_profile_file
        self.temp_dir.cleanup()

    @patch.object(SkillkorpK20Driver, "find_device", return_value="/dev/hidraw_test")
    @patch("os.path.exists", return_value=True)
    @patch("os.open", return_value=10)
    @patch("os.close")
    @patch("fcntl.ioctl", return_value=65)
    def test_set_rgb(self, mock_ioctl, mock_close, mock_open_fd, mock_exists, mock_find):
        driver = SkillkorpK20Driver()
        success = driver.set_rgb(mode="wave", speed=4, brightness=3, direction=1, color="#00FF00")
        self.assertTrue(success)
        self.assertTrue(mock_ioctl.called)
        args, _ = mock_ioctl.call_args
        buf = args[2]
        self.assertEqual(buf[0], 0x00)
        self.assertEqual(buf[1], CMD_SET_LEDPARAM)
        self.assertEqual(buf[2], 3)  # Wave code
        self.assertEqual(buf[3], 1)  # 5 - 4 = 1
        self.assertEqual(buf[4], 3)  # brightness
        self.assertEqual(buf[5], 1)  # direction
        self.assertEqual(buf[6], 0)  # R
        self.assertEqual(buf[7], 255) # G
        self.assertEqual(buf[8], 0)  # B

    @patch.object(SkillkorpK20Driver, "find_device", return_value="/dev/hidraw_test")
    @patch("os.path.exists", return_value=True)
    @patch("os.open", return_value=10)
    @patch("os.close")
    @patch("fcntl.ioctl", return_value=65)
    def test_set_polling_rate(self, mock_ioctl, mock_close, mock_open_fd, mock_exists, mock_find):
        driver = SkillkorpK20Driver()
        success = driver.set_polling_rate(500)
        self.assertTrue(success)
        args, _ = mock_ioctl.call_args
        buf = args[2]
        self.assertEqual(buf[1], CMD_SET_REPORT)
        self.assertEqual(buf[3], 2)  # 500Hz -> 2

    @patch.object(SkillkorpK20Driver, "find_device", return_value="/dev/hidraw_test")
    @patch("os.path.exists", return_value=True)
    @patch("os.open", return_value=10)
    @patch("os.close")
    @patch("fcntl.ioctl", return_value=65)
    def test_set_debounce(self, mock_ioctl, mock_close, mock_open_fd, mock_exists, mock_find):
        driver = SkillkorpK20Driver()
        success = driver.set_debounce(4)
        self.assertTrue(success)
        args, _ = mock_ioctl.call_args
        buf = args[2]
        self.assertEqual(buf[1], CMD_SET_DEBOUNCE)
        self.assertEqual(buf[3], 4)

    @patch.object(SkillkorpK20Driver, "find_device", return_value="/dev/hidraw_test")
    @patch("os.path.exists", return_value=True)
    @patch("os.open", return_value=10)
    @patch("os.close")
    @patch("fcntl.ioctl", return_value=65)
    def test_set_keyboard_options(self, mock_ioctl, mock_close, mock_open_fd, mock_exists, mock_find):
        driver = SkillkorpK20Driver()
        # Test with Win Lock On and Gaming Mode On
        success = driver.set_keyboard_options(win_lock=True, wasd_swap=False, os_mode="win", gaming_mode=True)
        self.assertTrue(success)
        args, _ = mock_ioctl.call_args
        buf = args[2]
        self.assertEqual(buf[1], CMD_SET_KBOPTION)
        bitfield = buf[3]
        self.assertTrue(bool(bitfield & (1 << 0)))  # win_lock bit
        self.assertTrue(bool(bitfield & (1 << 6)))  # gaming_mode bit
        self.assertFalse(bool(bitfield & (1 << 3))) # wasd_swap bit

    @patch.object(SkillkorpK20Driver, "find_device", return_value="/dev/hidraw_test")
    @patch("os.path.exists", return_value=True)
    @patch("os.open", return_value=10)
    @patch("os.close")
    @patch("fcntl.ioctl", return_value=65)
    def test_remap_key(self, mock_ioctl, mock_close, mock_open_fd, mock_exists, mock_find):
        # Spec: FEA_CMD_SET_KEYMATRIX_SIMPLE places the 4-byte action frame at buf[8..11].
        driver = SkillkorpK20Driver()
        success = driver.remap_key("F1", "media_vol_up")
        self.assertTrue(success)
        args, _ = mock_ioctl.call_args
        buf = args[2]
        self.assertEqual(buf[1], CMD_SET_KEYMATRIX_SIMPLE)
        self.assertEqual(buf[3], 1)  # F1 index is 1
        # media_vol_up action bytes = [3, 0, 233, 0]
        self.assertEqual(buf[8], 3)    # action byte 0
        self.assertEqual(buf[9], 0)    # action byte 1
        self.assertEqual(buf[10], 233) # action byte 2 (0xE9 volume up)
        self.assertEqual(buf[11], 0)   # action byte 3

    @patch.object(SkillkorpK20Driver, "find_device", return_value="/dev/hidraw_test")
    @patch("os.path.exists", return_value=True)
    @patch("os.open", return_value=10)
    @patch("os.close")
    @patch("fcntl.ioctl", return_value=65)
    def test_remap_fn_key(self, mock_ioctl, mock_close, mock_open_fd, mock_exists, mock_find):
        # Spec: FEA_CMD_SET_FN_SIMPLE uses the same buf[8..11] action frame layout as CMD_SET_KEYMATRIX_SIMPLE.
        driver = SkillkorpK20Driver()
        success = driver.remap_fn_key("Q", "mouse_left")
        self.assertTrue(success)
        args, _ = mock_ioctl.call_args
        buf = args[2]
        self.assertEqual(buf[1], CMD_SET_FN_SIMPLE)
        # mouse_left action bytes = [1, 0, 240, 0]
        self.assertEqual(buf[8], 1)
        self.assertEqual(buf[9], 0)
        self.assertEqual(buf[10], 240)
        self.assertEqual(buf[11], 0)

    @patch.object(SkillkorpK20Driver, "find_device", return_value="/dev/hidraw_test")
    @patch("os.path.exists", return_value=True)
    @patch("os.open", return_value=10)
    @patch("os.close")
    @patch("fcntl.ioctl", return_value=65)
    def test_set_sleep_time(self, mock_ioctl, mock_close, mock_open_fd, mock_exists, mock_find):
        # Spec: buf[8..9]=BT light sleep, buf[10..11]=2.4G light sleep,
        # buf[12..13]=BT deep sleep, buf[14..15]=2.4G deep sleep (all uint16 LE).
        driver = SkillkorpK20Driver()
        success = driver.set_sleep_time(light_sleep_sec=300, deep_sleep_sec=1680)
        self.assertTrue(success)
        args, _ = mock_ioctl.call_args
        buf = args[2]
        self.assertEqual(buf[1], CMD_SET_SLEEPTIME)

        light_lo, light_hi = 300 & 0xFF, (300 >> 8) & 0xFF
        deep_lo, deep_hi = 1680 & 0xFF, (1680 >> 8) & 0xFF

        self.assertEqual((buf[8], buf[9]), (light_lo, light_hi))     # BT light sleep
        self.assertEqual((buf[10], buf[11]), (light_lo, light_hi))   # 2.4G light sleep
        self.assertEqual((buf[12], buf[13]), (deep_lo, deep_hi))     # BT deep sleep
        self.assertEqual((buf[14], buf[15]), (deep_lo, deep_hi))     # 2.4G deep sleep

    @patch.object(SkillkorpK20Driver, "find_device", return_value="/dev/hidraw_test")
    @patch("os.path.exists", return_value=True)
    @patch("os.open", return_value=10)
    @patch("os.close")
    @patch("fcntl.ioctl", return_value=65)
    def test_factory_reset(self, mock_ioctl, mock_close, mock_open_fd, mock_exists, mock_find):
        driver = SkillkorpK20Driver()
        success = driver.factory_reset()
        self.assertTrue(success)
        args, _ = mock_ioctl.call_args
        buf = args[2]
        self.assertEqual(buf[1], CMD_SET_RESERT)


class TestProfileManager(unittest.TestCase):
    """Tests du gestionnaire multi-profils."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_profiles_dir = ProfileManager.__module__
        # Patch paths
        import profile_manager
        self.pm_mod = profile_manager
        self.orig_cfg_dir = profile_manager.CONFIG_DIR
        self.orig_prof_dir = profile_manager.PROFILES_DIR
        self.orig_state_file = profile_manager.STATE_FILE
        profile_manager.CONFIG_DIR = self.temp_dir.name
        profile_manager.PROFILES_DIR = os.path.join(self.temp_dir.name, "profiles")
        profile_manager.STATE_FILE = os.path.join(self.temp_dir.name, "state.json")

    def tearDown(self):
        self.pm_mod.CONFIG_DIR = self.orig_cfg_dir
        self.pm_mod.PROFILES_DIR = self.orig_prof_dir
        self.pm_mod.STATE_FILE = self.orig_state_file
        self.temp_dir.cleanup()

    def test_default_profiles_created(self):
        pm = ProfileManager()
        profs = pm.list_profiles()
        ids = [p["id"] for p in profs]
        self.assertIn("default", ids)
        self.assertIn("gaming", ids)
        self.assertIn("bureau", ids)
        self.assertIn("eco", ids)

    def test_create_and_delete_profile(self):
        pm = ProfileManager()
        p = pm.create_profile("test_game", "Test Game", copy_from="gaming")
        self.assertEqual(p["id"], "test_game")
        self.assertEqual(p["name"], "Test Game")
        self.assertIn("test_game", [x["id"] for x in pm.list_profiles()])

        deleted = pm.delete_profile("test_game")
        self.assertTrue(deleted)
        self.assertNotIn("test_game", [x["id"] for x in pm.list_profiles()])

    def test_cannot_delete_default(self):
        pm = ProfileManager()
        with self.assertRaises(ValueError):
            pm.delete_profile("default")

    def test_switch_profile(self):
        pm = ProfileManager()
        pm.switch_profile("gaming")
        self.assertEqual(pm.get_active_profile_id(), "gaming")


if __name__ == "__main__":
    unittest.main()
