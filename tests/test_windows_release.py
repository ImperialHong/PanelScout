from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from panelscout.windows_launcher import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WindowsLauncherTests(unittest.TestCase):
    def test_launcher_starts_server_without_browser(self):
        calls = []

        def fake_server(config, *, host, port):
            calls.append((config, host, port))

        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text("", encoding="utf-8")

            result = main(
                [
                    "--config",
                    str(config_path),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8766",
                    "--no-browser",
                    "--no-pause-on-exit",
                ],
                server_runner=fake_server,
            )

        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], ("127.0.0.1", 8766))
        self.assertEqual(os.environ["PLAYWRIGHT_BROWSERS_PATH"], "0")

    def test_launcher_reports_config_errors(self):
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text("metadata_only = false", encoding="utf-8")

            result = main(
                [
                    "--config",
                    str(config_path),
                    "--no-browser",
                    "--no-pause-on-exit",
                ],
                server_runner=lambda config, *, host, port: None,
            )

        self.assertEqual(result, 1)

    def test_launcher_opens_browser_after_port_is_ready(self):
        opened = []

        def fake_server(config, *, host, port):
            return None

        class ImmediateThread:
            def __init__(self, *, target, args, daemon):
                self.target = target
                self.args = args
                self.daemon = daemon

            def start(self):
                self.target(*self.args)

        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text("", encoding="utf-8")
            with (
                patch("panelscout.windows_launcher._is_port_open", return_value=True),
                patch("panelscout.windows_launcher.threading.Thread", ImmediateThread),
            ):
                result = main(
                    [
                        "--config",
                        str(config_path),
                        "--port",
                        "8767",
                        "--no-pause-on-exit",
                    ],
                    browser_open=lambda url: opened.append(url) or True,
                    server_runner=fake_server,
                )

        self.assertEqual(result, 0)
        self.assertEqual(opened, ["http://127.0.0.1:8767/"])


class WindowsPackagingTests(unittest.TestCase):
    def test_pyinstaller_spec_collects_playwright_and_launcher(self):
        spec = (PROJECT_ROOT / "packaging/windows/panelscout_windows.spec").read_text(
            encoding="utf-8"
        )

        self.assertIn("windows_launcher.py", spec)
        self.assertIn('name="PanelScout"', spec)
        self.assertIn('collect_all("playwright")', spec)

    def test_github_workflow_builds_and_uploads_portable_zip(self):
        workflow = (PROJECT_ROOT / ".github/workflows/windows-release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("windows-latest", workflow)
        self.assertIn("python -m playwright install chromium", workflow)
        self.assertIn("pyinstaller --clean --noconfirm", workflow)
        self.assertIn("Compress-Archive", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("gh release create", workflow)

    def test_windows_readme_documents_double_click_usage(self):
        readme = (PROJECT_ROOT / "packaging/windows/README-Windows.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Double-click `PanelScout.exe`", readme)
        self.assertIn("http://127.0.0.1:8765/", readme)
        self.assertIn("Passwords are not saved", readme)


if __name__ == "__main__":
    unittest.main()
