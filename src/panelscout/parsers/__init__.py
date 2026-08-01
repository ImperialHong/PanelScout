"""HTML parsers for saved public metadata fixtures."""

from panelscout.parsers.zaimanhua import (
    ParsedChapter,
    ParsedComicDetail,
    parse_detail_api_response,
    parse_detail_page,
    parse_search_api_response,
    parse_search_results,
)

__all__ = [
    "ParsedChapter",
    "ParsedComicDetail",
    "parse_detail_api_response",
    "parse_detail_page",
    "parse_search_api_response",
    "parse_search_results",
]
