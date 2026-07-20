from pathlib import Path
import unittest

from panelscout.config import DEFAULT_USER_AGENT, default_config
from panelscout.crawler.fetcher import (
    FetchBlockedError,
    FetchHTTPError,
    HtmlFetcher,
    NonHtmlContentError,
)
from panelscout.crawler.robots import RobotsDisallowedError, RobotsPolicy

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "zaimanhua"


class HtmlFetcherTests(unittest.TestCase):
    def setUp(self):
        text = (FIXTURE_ROOT / "robots.txt").read_text(encoding="utf-8")
        self.policy = RobotsPolicy.from_text(text)

    def test_fetches_html_with_config_user_agent(self):
        opener = FakeOpener([FakeResponse(body=b"<html>ok</html>")])
        fetcher = HtmlFetcher(
            config=default_config(),
            robots_policy=self.policy,
            opener=opener,
        )

        result = fetcher.fetch_html("https://manhua.zaimanhua.com/details/15599")

        self.assertEqual(result.text, "<html>ok</html>")
        self.assertEqual(opener.requests[0].get_header("User-agent"), DEFAULT_USER_AGENT)

    def test_disallowed_robots_url_does_not_open(self):
        opener = FakeOpener([FakeResponse()])
        fetcher = HtmlFetcher(
            robots_policy=self.policy,
            opener=opener,
        )

        with self.assertRaises(RobotsDisallowedError):
            fetcher.fetch_html("https://manhua.zaimanhua.com/api/search")

        self.assertEqual(opener.requests, [])

    def test_rejects_non_html_response(self):
        opener = FakeOpener(
            [
                FakeResponse(
                    headers={"Content-Type": "application/json"},
                    body=b"{}",
                )
            ]
        )
        fetcher = HtmlFetcher(
            robots_policy=self.policy,
            opener=opener,
        )

        with self.assertRaises(NonHtmlContentError):
            fetcher.fetch_html("https://manhua.zaimanhua.com/details/15599")

    def test_rejects_blocked_status(self):
        opener = FakeOpener([FakeResponse(status=429)])
        fetcher = HtmlFetcher(
            robots_policy=self.policy,
            opener=opener,
        )

        with self.assertRaises(FetchBlockedError):
            fetcher.fetch_html("https://manhua.zaimanhua.com/details/15599")

    def test_rejects_other_http_error_status(self):
        opener = FakeOpener([FakeResponse(status=500)])
        fetcher = HtmlFetcher(
            robots_policy=self.policy,
            opener=opener,
        )

        with self.assertRaises(FetchHTTPError):
            fetcher.fetch_html("https://manhua.zaimanhua.com/details/15599")

    def test_honors_robots_crawl_delay_between_same_host_requests(self):
        opener = FakeOpener([FakeResponse(), FakeResponse()])
        sleeper = FakeSleeper()
        clock = FakeClock([100.0, 100.25, 101.0])
        fetcher = HtmlFetcher(
            robots_policy=self.policy,
            opener=opener,
            request_delay_seconds=0,
            sleeper=sleeper,
            monotonic=clock,
        )

        fetcher.fetch_html("https://manhua.zaimanhua.com/details/15599")
        fetcher.fetch_html("https://manhua.zaimanhua.com/dynamic/sample")

        self.assertEqual(sleeper.calls, [0.75])
        self.assertEqual(fetcher.crawl_delay(), 1.0)


class FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"<html></html>",
    ) -> None:
        self.status = status
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self._body = body

    def read(self) -> bytes:
        return self._body


class FakeOpener:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append(request)
        return self.responses.pop(0)


class FakeSleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(round(seconds, 2))


class FakeClock:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def __call__(self) -> float:
        return self.values.pop(0)


if __name__ == "__main__":
    unittest.main()
