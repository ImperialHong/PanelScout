"""Robots.txt parsing and public URL policy checks."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from urllib.parse import urlparse

from panelscout.config import DEFAULT_USER_AGENT


@dataclass(frozen=True)
class RobotsPolicy:
    """Parsed robots.txt rules for a single site."""

    groups: tuple["RobotsGroup", ...]
    robots_url: str | None = None

    @classmethod
    def from_text(cls, text: str, *, robots_url: str | None = None) -> "RobotsPolicy":
        """Parse robots.txt text into a policy object."""

        groups: list[RobotsGroup] = []
        current_agents: list[str] = []
        current_rules: list[RobotsRule] = []
        current_crawl_delay: float | None = None
        has_directive = False

        def flush_group() -> None:
            nonlocal current_agents, current_rules, current_crawl_delay, has_directive
            if current_agents:
                groups.append(
                    RobotsGroup(
                        user_agents=tuple(current_agents),
                        rules=tuple(current_rules),
                        crawl_delay=current_crawl_delay,
                    )
                )
            current_agents = []
            current_rules = []
            current_crawl_delay = None
            has_directive = False

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                if current_agents and has_directive:
                    flush_group()
                current_agents.append(value.lower())
                continue

            if not current_agents:
                continue

            if key in {"allow", "disallow"}:
                has_directive = True
                if value:
                    current_rules.append(
                        RobotsRule(
                            pattern=value,
                            allowed=key == "allow",
                        )
                    )
            elif key == "crawl-delay":
                has_directive = True
                current_crawl_delay = _parse_delay(value)

        flush_group()
        return cls(groups=tuple(groups), robots_url=robots_url)

    def can_fetch(
        self,
        url: str,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> bool:
        """Return whether the user agent may fetch the URL."""

        group = self._matching_group(user_agent)
        if group is None:
            return True

        path = _path_for_matching(url)
        matching_rules = [rule for rule in group.rules if rule.matches(path)]
        if not matching_rules:
            return True

        best_rule = max(
            matching_rules,
            key=lambda rule: (rule.match_length, 1 if rule.allowed else 0),
        )
        return best_rule.allowed

    def assert_allowed(
        self,
        url: str,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        """Raise if robots.txt disallows fetching the URL."""

        if not self.can_fetch(url, user_agent=user_agent):
            raise RobotsDisallowedError(f"Robots policy disallows {url}")

    def crawl_delay(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> float | None:
        """Return the matching crawl-delay in seconds, if one exists."""

        group = self._matching_group(user_agent)
        return group.crawl_delay if group is not None else None

    def _matching_group(self, user_agent: str) -> "RobotsGroup | None":
        user_agent = user_agent.lower()
        matches = [
            group
            for group in self.groups
            if group.matches_user_agent(user_agent)
        ]
        if not matches:
            return None
        return max(matches, key=lambda group: group.match_score(user_agent))


@dataclass(frozen=True)
class RobotsGroup:
    """A robots.txt user-agent group."""

    user_agents: tuple[str, ...]
    rules: tuple["RobotsRule", ...] = ()
    crawl_delay: float | None = None

    def matches_user_agent(self, user_agent: str) -> bool:
        return any(agent == "*" or agent in user_agent for agent in self.user_agents)

    def match_score(self, user_agent: str) -> int:
        scores = [
            len(agent)
            for agent in self.user_agents
            if agent == "*" or agent in user_agent
        ]
        return max(scores) if scores else -1


@dataclass(frozen=True)
class RobotsRule:
    """One Allow or Disallow rule."""

    pattern: str
    allowed: bool
    _regex: re.Pattern[str] = field(init=False, repr=False)
    match_length: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "match_length", len(self.pattern))
        object.__setattr__(self, "_regex", re.compile(_pattern_to_regex(self.pattern)))

    def matches(self, path: str) -> bool:
        return bool(self._regex.match(path))


class RobotsDisallowedError(PermissionError):
    """Raised when robots.txt disallows a URL."""


def _parse_delay(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _path_for_matching(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _pattern_to_regex(pattern: str) -> str:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]

    regex = re.escape(pattern).replace(r"\*", ".*")
    suffix = "$" if anchored else ""
    return f"^{regex}{suffix}"
