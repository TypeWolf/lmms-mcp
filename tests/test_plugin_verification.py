"""Regression tests for plugin verification, independent of an LMMS install."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from lmms_mcp import lmms_app, server
from lmms_mcp.project import LMMSProject


class PluginVerificationTests(unittest.TestCase):
    def setUp(self):
        # Never probe or execute the workstation's application during unit tests.
        self.exe = patch.object(lmms_app, "find_lmms_exe", return_value=Path("/test/lmms"))
        self.version = patch.object(lmms_app, "get_lmms_version", return_value="1.2.2")
        self.exe.start()
        self.version.start()
        self.addCleanup(self.exe.stop)
        self.addCleanup(self.version.stop)
        self.previous_project = server.get_project()
        project = LMMSProject()
        project.new()
        server.set_project(project)
        self.addCleanup(server.set_project, self.previous_project)

    def test_empty_inventory_does_not_verify_any_plugins(self):
        with patch.object(lmms_app, "get_installed_plugins", return_value=set()):
            info = json.loads(server.get_lmms_info())
        self.assertEqual(info["instruments_verified_available"], [])
        self.assertEqual(info["effects_verified_available"], [])

    def test_missing_application_is_not_verified(self):
        with patch.object(lmms_app, "find_lmms_exe", return_value=None):
            info = json.loads(server.get_lmms_info())
        self.assertFalse(info["found"])
        self.assertEqual(info.get("instruments_verified_available", []), [])

    def test_detected_plugin_and_alias_remain_verified(self):
        inventory = {"tripleoscillator", "papu", "delay"}
        with patch.object(lmms_app, "get_installed_plugins", return_value=inventory):
            info = json.loads(server.get_lmms_info())
        self.assertIn("tripleoscillator", info["instruments_verified_available"])
        self.assertIn("nes", info["instruments_verified_available"])
        self.assertIn("delay", info["effects_verified_available"])
        self.assertNotIn("slicert", info["instruments_verified_available"])

    def test_static_plugin_assumption_is_not_verification(self):
        with patch.object(lmms_app, "get_installed_plugins", return_value={"tripleoscillator"}):
            info = json.loads(server.get_lmms_info())
        self.assertNotIn("freeboy", info["instruments_verified_available"])

    def test_offline_composition_still_adds_an_instrument(self):
        with patch.object(lmms_app, "get_installed_plugins", return_value=set()):
            result = json.loads(server.add_instrument_track("Offline lead"))
        self.assertNotIn("error", result)
        self.assertEqual(len(server.get_project().get_info().tracks), 1)

    def test_offline_composition_reports_unknown_availability(self):
        with patch.object(lmms_app, "get_installed_plugins", return_value=set()):
            result = json.loads(server.add_instrument_track("Offline lead"))
        self.assertIn("cannot verify", result["warning"])

    def test_offline_effects_remain_allowed_with_a_warning(self):
        with patch.object(lmms_app, "get_installed_plugins", return_value=set()):
            server.add_instrument_track("Offline lead")
            result = json.loads(server.add_effect("track", 0, "delay"))
        self.assertNotIn("error", result)
        self.assertIn("cannot verify", result["warning"])

    def test_unknown_status_is_distinct_from_missing(self):
        unknown, _ = lmms_app.get_plugin_availability("slicert", installed_plugins=set())
        missing, _ = lmms_app.get_plugin_availability("slicert", installed_plugins={"delay"})
        self.assertIsNone(unknown)
        self.assertIs(missing, False)

    def test_legacy_boolean_remains_permissive_for_offline_callers(self):
        with patch.object(lmms_app, "get_installed_plugins", return_value=set()):
            allowed, reason = lmms_app.check_plugin_available("tripleoscillator")
        self.assertIs(allowed, True)
        self.assertIn("cannot verify", reason)

    def test_unreadable_inventory_is_unknown_instead_of_verified(self):
        with patch.object(lmms_app, "get_installed_plugins", side_effect=PermissionError):
            status, reason = lmms_app.get_plugin_availability("tripleoscillator")
            info = json.loads(server.get_lmms_info())
        self.assertIsNone(status)
        self.assertIn("cannot verify", reason)
        self.assertEqual(info["plugin_inventory_status"], "unknown")
        self.assertEqual(info["instruments_verified_available"], [])
        self.assertTrue(info["plugin_inventory_warning"])

    def test_info_uses_one_consistent_inventory_snapshot(self):
        with patch.object(lmms_app, "get_installed_plugins", return_value={"delay"}) as query:
            info = json.loads(server.get_lmms_info())
        query.assert_called_once_with()
        self.assertEqual(info["plugin_inventory_status"], "available")
        self.assertIn("freeboy", info["instruments_unverified"])
        self.assertNotIn("slicert", info["instruments_verified_available"])

    def test_static_candidate_is_detected_if_its_file_is_present(self):
        status, _ = lmms_app.get_plugin_availability("freeboy", installed_plugins={"freeboy"})
        self.assertIs(status, True)


if __name__ == "__main__":
    unittest.main()
