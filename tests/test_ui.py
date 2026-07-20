from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.ui import build_local_ui_shell, write_local_ui_shell
from panelscout.ui.shell import DOWNLOAD_LAYOUT_PREVIEW, NAV_ITEMS


class LocalUiShellTests(unittest.TestCase):
    def test_static_shell_contains_mvp4_navigation_and_sections(self):
        html = build_local_ui_shell()

        for item in NAV_ITEMS:
            self.assertIn(f">{item}<", html)
        self.assertIn('id="search"', html)
        self.assertIn('id="local-library"', html)
        self.assertIn('id="watchlist"', html)
        self.assertIn('id="update-history"', html)
        self.assertIn('id="downloads"', html)
        self.assertIn('id="settings"', html)

    def test_download_area_is_planned_and_uses_expected_folder_preview(self):
        html = build_local_ui_shell()

        self.assertIn(DOWNLOAD_LAYOUT_PREVIEW, html)
        self.assertIn("Download selected chapters - planned", html)
        self.assertIn("Retry failed - planned", html)
        self.assertIn("disabled", html)
        self.assertIn("no downloader engine is active", html)

    def test_write_local_ui_shell_creates_parent_directories(self):
        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "nested" / "panelscout-ui.html"

            written = write_local_ui_shell(output_path)
            html = output_path.read_text(encoding="utf-8")

        self.assertEqual(written, output_path)
        self.assertIn("<title>PanelScout Local UI</title>", html)
        self.assertIn(DOWNLOAD_LAYOUT_PREVIEW, html)


if __name__ == "__main__":
    unittest.main()
