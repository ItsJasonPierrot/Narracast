"""Tests for narracast.platform — cross-platform shell helpers."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestPathToFileUri(unittest.TestCase):
    def _call(self, path: str) -> str:
        from narracast.platform import _path_to_file_uri
        return _path_to_file_uri(path)

    def test_simple_posix_path(self) -> None:
        uri = self._call("/home/user/audio/file.mp3")
        self.assertTrue(uri.startswith("file:///"))
        self.assertIn("file.mp3", uri)

    def test_path_with_spaces(self) -> None:
        uri = self._call("/home/user/my music/track.mp3")
        self.assertTrue(uri.startswith("file:///"))
        # Space must be percent-encoded
        self.assertNotIn(" ", uri)

    def test_path_with_special_chars(self) -> None:
        uri = self._call("/tmp/café/track.mp3")
        self.assertTrue(uri.startswith("file:///"))
        self.assertNotIn(" ", uri)


class TestRevealLabel(unittest.TestCase):
    def test_macos_label(self) -> None:
        with patch("platform.system", return_value="Darwin"):
            from importlib import reload
            import narracast.platform as mod
            reload(mod)
            self.assertEqual(mod.reveal_label(), "Reveal in Finder")

    def test_windows_label(self) -> None:
        with patch("platform.system", return_value="Windows"):
            from importlib import reload
            import narracast.platform as mod
            reload(mod)
            self.assertEqual(mod.reveal_label(), "Show in Explorer")

    def test_linux_label(self) -> None:
        with patch("platform.system", return_value="Linux"):
            from importlib import reload
            import narracast.platform as mod
            reload(mod)
            self.assertEqual(mod.reveal_label(), "Show in Files")

    def tearDown(self) -> None:
        # Reload with real platform so other tests are unaffected
        from importlib import reload
        import narracast.platform as mod
        reload(mod)


class TestLogDir(unittest.TestCase):
    def test_macos_log_dir(self) -> None:
        with patch("platform.system", return_value="Darwin"):
            from importlib import reload
            import narracast.platform as mod
            reload(mod)
            result = mod.log_dir()
            self.assertEqual(result, Path.home() / "Library" / "Logs")

    def test_windows_log_dir_uses_localappdata(self) -> None:
        env = {"LOCALAPPDATA": "C:\\Users\\user\\AppData\\Local"}
        with patch("platform.system", return_value="Windows"), patch.dict("os.environ", env, clear=False):
            from importlib import reload
            import narracast.platform as mod
            reload(mod)
            result = mod.log_dir()
            self.assertIn("Narracast", str(result))
            self.assertIn("Logs", str(result))

    def test_linux_log_dir_default(self) -> None:
        with patch("platform.system", return_value="Linux"), patch.dict("os.environ", {}, clear=False):
            from importlib import reload
            import narracast.platform as mod
            reload(mod)
            result = mod.log_dir()
            self.assertIn("narracast", str(result))
            self.assertIn("logs", str(result))

    def test_linux_log_dir_respects_xdg_state_home(self) -> None:
        env = {"XDG_STATE_HOME": "/custom/state"}
        with patch("platform.system", return_value="Linux"), patch.dict("os.environ", env):
            from importlib import reload
            import narracast.platform as mod
            reload(mod)
            result = mod.log_dir()
            self.assertTrue(str(result).startswith("/custom/state"))

    def tearDown(self) -> None:
        from importlib import reload
        import narracast.platform as mod
        reload(mod)


class TestPlayAudio(unittest.TestCase):
    def _play(self, path: str = "/tmp/test.mp3") -> MagicMock:
        from narracast.platform import play_audio
        return play_audio(path)

    def test_macos_uses_afplay(self) -> None:
        with patch("platform.system", return_value="Darwin"), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            self._play()
            cmd = mock_popen.call_args[0][0]
            self.assertEqual(cmd[0], "afplay")
            self.assertIn("test.mp3", cmd[-1])

    def test_linux_uses_ffplay_when_available(self) -> None:
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", side_effect=lambda x: "/usr/bin/ffplay" if x == "ffplay" else None), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            self._play()
            cmd = mock_popen.call_args[0][0]
            self.assertIn("ffplay", cmd[0])
            self.assertIn("-nodisp", cmd)

    def test_linux_uses_mpg123_fallback(self) -> None:
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", side_effect=lambda x: "/usr/bin/mpg123" if x == "mpg123" else None), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            self._play()
            cmd = mock_popen.call_args[0][0]
            self.assertIn("mpg123", cmd[0])

    def test_linux_raises_when_no_player(self) -> None:
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value=None):
            from narracast.platform import play_audio
            with self.assertRaises(RuntimeError) as ctx:
                play_audio("/tmp/test.mp3")
            self.assertIn("audio player", str(ctx.exception).lower())

    def test_windows_uses_powershell_with_uri(self) -> None:
        with patch("platform.system", return_value="Windows"), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            from narracast.platform import play_audio
            play_audio("C:\\Users\\user\\test.mp3")
            cmd = mock_popen.call_args[0][0]
            self.assertEqual(cmd[0], "powershell")
            ps_command = " ".join(cmd)
            # Should use a file:// URI, not raw path interpolation
            self.assertIn("file://", ps_command)
            self.assertIn("MediaPlayer", ps_command)


class TestRevealPath(unittest.TestCase):
    def test_macos_uses_open_R(self) -> None:
        with patch("platform.system", return_value="Darwin"), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            from narracast.platform import reveal_path
            reveal_path("/tmp/test.mp3")
            cmd = mock_popen.call_args[0][0]
            self.assertIn("open", cmd)
            self.assertIn("-R", cmd)

    def test_windows_uses_explorer_select(self) -> None:
        with patch("platform.system", return_value="Windows"), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            from narracast.platform import reveal_path
            reveal_path("C:\\Users\\user\\test.mp3")
            cmd = mock_popen.call_args[0][0]
            self.assertIn("explorer", cmd[0])
            self.assertIn("/select,", cmd[1])

    def test_linux_raises_without_xdg_open(self) -> None:
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value=None):
            from narracast.platform import reveal_path
            with self.assertRaises(RuntimeError):
                reveal_path("/tmp/test.mp3")

    def test_linux_opens_parent_folder_with_xdg_open(self) -> None:
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value="/usr/bin/xdg-open"), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            from narracast.platform import reveal_path
            reveal_path("/tmp/subdir/test.mp3")
            cmd = mock_popen.call_args[0][0]
            self.assertIn("xdg-open", cmd[0])
            # Opens the parent directory, not the file itself
            self.assertIn("/tmp/subdir", cmd[-1])


class TestOpenFolder(unittest.TestCase):
    def test_macos_uses_open(self) -> None:
        with patch("platform.system", return_value="Darwin"), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            from narracast.platform import open_folder
            open_folder("/tmp/output")
            cmd = mock_popen.call_args[0][0]
            self.assertEqual(cmd, ["open", "/tmp/output"])

    def test_windows_uses_explorer(self) -> None:
        with patch("platform.system", return_value="Windows"), \
             patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            from narracast.platform import open_folder
            open_folder("C:\\output")
            cmd = mock_popen.call_args[0][0]
            self.assertIn("explorer", cmd[0])

    def test_linux_raises_without_xdg_open(self) -> None:
        with patch("platform.system", return_value="Linux"), \
             patch("shutil.which", return_value=None):
            from narracast.platform import open_folder
            with self.assertRaises(RuntimeError):
                open_folder("/tmp/output")


class TestLogDirPathsConsistency(unittest.TestCase):
    """Verify paths.LOG_DIR and platform.log_dir() return the same value."""

    def test_log_dir_sources_agree(self) -> None:
        from narracast.paths import LOG_DIR
        from narracast.platform import log_dir
        self.assertEqual(LOG_DIR, log_dir())


if __name__ == "__main__":
    unittest.main()
