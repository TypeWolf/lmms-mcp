"""Portable discovery tests: inspect files without loading native plugins."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lmms_mcp import lmms_app


class LinuxDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # Do not let workstation configuration influence unit tests.
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def executable(self, relative):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# discovery fixture; never executed\n")
        path.chmod(0o755)
        return path

    def test_executable_override_is_read_at_call_time(self):
        first = self.executable("first.AppImage")
        second = self.executable("second.AppImage")
        for candidate in (first, second):
            with patch.dict(os.environ, {"LMMS_EXECUTABLE": str(candidate)}):
                self.assertEqual(lmms_app.find_lmms_exe(), candidate)

    def test_invalid_override_does_not_select_another_installation(self):
        other = self.executable("other/lmms")
        with patch.dict(os.environ, {"LMMS_EXECUTABLE": str(self.root / "missing")}):
            with patch("shutil.which", return_value=str(other)):
                self.assertIsNone(lmms_app.find_lmms_exe())

    @unittest.skipIf(os.name == "nt", "POSIX executable permissions")
    def test_non_executable_override_is_rejected(self):
        path = self.executable("not-executable")
        path.chmod(0o644)
        with patch.dict(os.environ, {"LMMS_EXECUTABLE": str(path)}):
            self.assertIsNone(lmms_app.find_lmms_exe())

    def test_lmms_on_path_is_discovered(self):
        executable = self.executable("bin/lmms")
        with (
            patch("shutil.which", return_value=str(executable)),
            patch.object(lmms_app, "_is_executable", return_value=False),
        ):
            self.assertEqual(lmms_app.find_lmms_exe(), executable)

    def test_explicit_plugin_directory_works_without_an_executable(self):
        plugins = self.root / "plugins"
        plugins.mkdir()
        with patch.dict(os.environ, {"LMMS_PLUGIN_DIR": str(plugins)}):
            self.assertEqual(lmms_app.get_plugins_dir(), plugins)

    def test_invalid_plugin_override_does_not_fall_back(self):
        executable = self.executable("prefix/bin/lmms")
        (self.root / "prefix/lib/lmms").mkdir(parents=True)
        with patch.dict(os.environ, {"LMMS_PLUGIN_DIR": str(self.root / "missing")}):
            with patch.object(lmms_app, "find_lmms_exe", return_value=executable):
                self.assertIsNone(lmms_app.get_plugins_dir())

    def test_unix_prefix_plugin_directory(self):
        executable = self.executable("prefix/bin/lmms")
        plugins = self.root / "prefix/lib/lmms"
        plugins.mkdir(parents=True)
        with patch.object(lmms_app, "find_lmms_exe", return_value=executable):
            self.assertEqual(lmms_app.get_plugins_dir(), plugins)

    def test_portable_windows_style_directory_is_preserved(self):
        executable = self.executable("portable/lmms.exe")
        plugins = executable.parent / "plugins"
        plugins.mkdir()
        with patch.object(lmms_app, "find_lmms_exe", return_value=executable):
            self.assertEqual(lmms_app.get_plugins_dir(), plugins)

    def test_multiarch_inventory_uses_selected_prefix(self):
        executable = self.executable("prefix/bin/lmms")
        for multiarch in ("x86_64-linux-gnu", "aarch64-linux-gnu"):
            with self.subTest(multiarch=multiarch):
                plugins = self.root / "prefix/lib" / multiarch / "lmms"
                plugins.mkdir(parents=True)
                (plugins / "libtripleoscillator.so").touch()
                with (
                    patch.object(lmms_app, "find_lmms_exe", return_value=executable),
                    patch("sysconfig.get_config_var", return_value=multiarch),
                ):
                    self.assertEqual(lmms_app.get_plugins_dir(), plugins)
                    self.assertEqual(lmms_app.get_installed_plugins(), {"tripleoscillator"})

    def test_multiarch_does_not_select_another_abi(self):
        executable = self.executable("prefix/bin/lmms")
        (self.root / "prefix/lib/aarch64-linux-gnu/lmms").mkdir(parents=True)
        with (
            patch.object(lmms_app, "find_lmms_exe", return_value=executable),
            patch("sysconfig.get_config_var", return_value="x86_64-linux-gnu"),
        ):
            self.assertIsNone(lmms_app.get_plugins_dir())

    def test_missing_multiarch_value_does_not_scan_other_directories(self):
        executable = self.executable("prefix/bin/lmms")
        (self.root / "prefix/lib/x86_64-linux-gnu/lmms").mkdir(parents=True)
        with (
            patch.object(lmms_app, "find_lmms_exe", return_value=executable),
            patch("sysconfig.get_config_var", return_value=None),
        ):
            self.assertIsNone(lmms_app.get_plugins_dir())

    def test_plain_layout_keeps_priority_over_multiarch(self):
        executable = self.executable("prefix/bin/lmms")
        plugins = self.root / "prefix/lib/lmms"
        plugins.mkdir(parents=True)
        (self.root / "prefix/lib/x86_64-linux-gnu/lmms").mkdir(parents=True)
        with (
            patch.object(lmms_app, "find_lmms_exe", return_value=executable),
            patch("sysconfig.get_config_var", return_value="x86_64-linux-gnu"),
        ):
            self.assertEqual(lmms_app.get_plugins_dir(), plugins)

    @unittest.skipIf(os.name == "nt", "POSIX AppDir symlink layout")
    def test_extracted_appdir_resolves_apprun_for_plugin_paths(self):
        self.executable("app/usr/bin/lmms")
        plugins = self.root / "app/usr/lib/lmms"
        plugins.mkdir(parents=True)
        apprun = self.root / "app/AppRun"
        apprun.symlink_to("usr/bin/lmms")
        with patch.object(lmms_app, "find_lmms_exe", return_value=apprun):
            self.assertEqual(lmms_app.get_plugins_dir(), plugins)

    def test_appimage_does_not_borrow_an_unrelated_prefix_inventory(self):
        executable = self.executable("prefix/bin/lmms.AppImage")
        (self.root / "prefix/lib/lmms").mkdir(parents=True)
        with patch.object(lmms_app, "find_lmms_exe", return_value=executable):
            self.assertIsNone(lmms_app.get_plugins_dir())

    def test_shared_library_names_are_normalized_without_loading(self):
        plugins = self.root / "plugins"
        plugins.mkdir()
        for name in ("libtripleoscillator.so", "libpapu.so", "delay.dll", "libghost.so.1", "README.txt"):
            (plugins / name).touch()
        (plugins / "libdirectory.so").mkdir()
        with patch.object(lmms_app, "get_plugins_dir", return_value=plugins):
            self.assertEqual(lmms_app.get_installed_plugins(), {"tripleoscillator", "papu", "delay"})

    def test_failed_process_is_not_a_version(self):
        process = subprocess.CompletedProcess([], 1, stdout="", stderr="Missing GLIBC_2.38")
        with patch.object(lmms_app, "find_lmms_exe", return_value=Path("/test/lmms")):
            with patch.object(lmms_app.subprocess, "run", return_value=process):
                self.assertIsNone(lmms_app.get_lmms_version())

    def test_successful_non_lmms_output_is_not_a_version(self):
        process = subprocess.CompletedProcess([], 0, stdout="Helper 2.38", stderr="")
        with patch.object(lmms_app, "find_lmms_exe", return_value=Path("/test/lmms")):
            with patch.object(lmms_app.subprocess, "run", return_value=process):
                self.assertIsNone(lmms_app.get_lmms_version())

    def test_wrapper_messages_do_not_hide_lmms_version(self):
        process = subprocess.CompletedProcess([], 0, stdout="Wrapper notice\nLMMS 1.2.2\n", stderr="")
        with patch.object(lmms_app, "find_lmms_exe", return_value=Path("/test/lmms")):
            with patch.object(lmms_app.subprocess, "run", return_value=process):
                self.assertEqual(lmms_app.get_lmms_version(), "1.2.2")


if __name__ == "__main__":
    unittest.main()
