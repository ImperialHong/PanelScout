from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panelscout import __version__
from panelscout.cli import main


def run_cli(args):
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_version_flag(self):
        code, stdout, stderr = run_cli(["--version"])

        self.assertEqual(code, 0)
        self.assertIn(__version__, stdout)
        self.assertEqual(stderr, "")

    def test_config_show_json_uses_config_file(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[paths]",
                        f'data_dir = "{root / "data"}"',
                        "[network]",
                        "request_delay_seconds = 1.25",
                    ]
                ),
                encoding="utf-8",
            )

            code, stdout, stderr = run_cli(
                ["--config", str(config_path), "config", "show", "--json"]
            )

        self.assertEqual(code, 0)
        self.assertIn('"request_delay_seconds": 1.25', stdout)
        self.assertIn('"metadata_only": true', stdout)
        self.assertEqual(stderr, "")

    def test_config_defaults_to_show(self):
        code, stdout, stderr = run_cli(["config"])

        self.assertEqual(code, 0)
        self.assertIn("metadata_only=True", stdout)
        self.assertEqual(stderr, "")

    def test_search_is_placeholder_without_network(self):
        code, stdout, stderr = run_cli(["search", "sample"])

        self.assertEqual(code, 0)
        self.assertIn("'search' is reserved", stdout)
        self.assertIn("No network request was made", stdout)
        self.assertEqual(stderr, "")


if __name__ == "__main__":
    unittest.main()
