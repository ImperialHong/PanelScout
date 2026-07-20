from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout.config import ConfigError, build_config, default_config, load_config


class ConfigTests(unittest.TestCase):
    def test_default_config_is_metadata_only_and_local(self):
        config = default_config()

        self.assertTrue(config.metadata_only)
        self.assertEqual(config.source, "zaimanhua")
        self.assertEqual(config.database_path.name, "panelscout.sqlite3")
        self.assertEqual(config.session_dir.name, "sessions")
        self.assertEqual(config.download_root, Path.home() / "Downloads")
        self.assertGreaterEqual(config.request_delay_seconds, 1)
        self.assertEqual(config.max_concurrency_per_domain, 1)

    def test_load_config_applies_path_defaults_from_data_dir(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.toml"
            data_dir = root / "panel-data"
            config_path.write_text(
                "\n".join(
                    [
                        "[panelscout]",
                        f'data_dir = "{data_dir}"',
                        "request_delay_seconds = 1.5",
                        "max_concurrency_per_domain = 2",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

        self.assertEqual(config.data_dir, data_dir)
        self.assertEqual(config.database_path, data_dir / "panelscout.sqlite3")
        self.assertEqual(config.session_dir, data_dir / "sessions")
        self.assertEqual(config.download_root, Path.home() / "Downloads")
        self.assertEqual(config.request_delay_seconds, 1.5)
        self.assertEqual(config.max_concurrency_per_domain, 2)

    def test_load_config_accepts_custom_download_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.toml"
            download_root = root / "downloads"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'download_root = "{download_root}"',
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

        self.assertEqual(config.download_root, download_root)

    def test_rejects_non_metadata_only_config(self):
        with self.assertRaisesRegex(ConfigError, "metadata_only"):
            build_config({"metadata_only": False})

    def test_rejects_aggressive_concurrency(self):
        with self.assertRaisesRegex(ConfigError, "max_concurrency"):
            build_config({"max_concurrency_per_domain": 3})


if __name__ == "__main__":
    unittest.main()
