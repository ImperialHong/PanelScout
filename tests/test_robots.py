from pathlib import Path
import unittest

from panelscout.crawler.robots import (
    RobotsDisallowedError,
    RobotsLoadError,
    RobotsPolicy,
    load_robots_policy,
)

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

    def test_loads_policy_through_injected_opener(self):
        text = (FIXTURE_ROOT / "robots.txt").read_text(encoding="utf-8")
        opener = FakeRobotsOpener(
            FakeRobotsResponse(body=text.encode("utf-8"))
        )

        policy = load_robots_policy(
            "https://manhua.zaimanhua.com/robots.txt",
            opener=opener,
            user_agent="PanelScout/0.1",
        )

        self.assertEqual(policy.crawl_delay(), 1.0)
        self.assertEqual(opener.requests[0].get_header("User-agent"), "PanelScout/0.1")

    def test_load_policy_fails_closed_on_bad_status(self):
        opener = FakeRobotsOpener(FakeRobotsResponse(status=500))

        with self.assertRaises(RobotsLoadError):
            load_robots_policy(
                "https://manhua.zaimanhua.com/robots.txt",
                opener=opener,
            )


class FakeRobotsResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"User-agent: *\nDisallow:",
    ) -> None:
        self.status = status
        self.headers = headers or {"Content-Type": "text/plain; charset=utf-8"}
        self._body = body

    def read(self) -> bytes:
        return self._body


class FakeRobotsOpener:
    def __init__(self, response: FakeRobotsResponse) -> None:
        self.response = response
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append(request)
        return self.response


if __name__ == "__main__":
    unittest.main()
