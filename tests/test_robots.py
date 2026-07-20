from pathlib import Path
import unittest

from panelscout.crawler.robots import RobotsDisallowedError, RobotsPolicy

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"


class RobotsPolicyTests(unittest.TestCase):
    def setUp(self):
        text = (FIXTURE_ROOT / "robots.txt").read_text(encoding="utf-8")
        self.policy = RobotsPolicy.from_text(
            text,
            robots_url="https://manhua.zaimanhua.com/robots.txt",
        )

    def test_allows_public_metadata_paths(self):
        self.assertTrue(
            self.policy.can_fetch("https://manhua.zaimanhua.com/dynamic/%E4%BC%AA%E6%81%8B")
        )
        self.assertTrue(
            self.policy.can_fetch("https://manhua.zaimanhua.com/details/15599")
        )

    def test_rejects_disallowed_paths(self):
        self.assertFalse(
            self.policy.can_fetch("https://manhua.zaimanhua.com/api/search")
        )
        self.assertFalse(
            self.policy.can_fetch("https://manhua.zaimanhua.com/dingyue/")
        )
        self.assertFalse(
            self.policy.can_fetch("https://manhua.zaimanhua.com/_nuxt/entry.js")
        )

    def test_exposes_crawl_delay(self):
        self.assertEqual(self.policy.crawl_delay(), 1.0)

    def test_assert_allowed_raises_for_disallowed_url(self):
        with self.assertRaises(RobotsDisallowedError):
            self.policy.assert_allowed("https://manhua.zaimanhua.com/api/search")

    def test_longest_matching_rule_wins(self):
        policy = RobotsPolicy.from_text(
            "\n".join(
                [
                    "User-agent: *",
                    "Allow: /",
                    "Disallow: /private/",
                    "Allow: /private/public/",
                    "Crawl-delay: 2",
                ]
            )
        )

        self.assertFalse(policy.can_fetch("https://example.test/private/item"))
        self.assertTrue(policy.can_fetch("https://example.test/private/public/item"))
        self.assertEqual(policy.crawl_delay(), 2.0)


if __name__ == "__main__":
    unittest.main()
