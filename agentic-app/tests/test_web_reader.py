"""
Tests for skills/web_reader.py helper behavior.
"""
from skills.web_reader import _collect_search_result, _normalize_result_url


def test_normalize_duckduckgo_redirect_url():
    href = (
        "https://duckduckgo.com/l/?uddg="
        "https%3A%2F%2Fexample.com%2Farticle%3Fx%3D1%26y%3D2"
    )
    assert _normalize_result_url(href) == "https://example.com/article?x=1&y=2"


def test_normalize_protocol_relative_url():
    assert _normalize_result_url("//example.com/path") == "https://example.com/path"


def test_collect_search_result_deduplicates_and_limits():
    results: list[dict[str, str]] = []

    _collect_search_result(results, "First", "https://example.com/a", max_results=2)
    _collect_search_result(results, "Dup", "https://example.com/a", max_results=2)
    _collect_search_result(results, "Second", "https://example.com/b", max_results=2)
    _collect_search_result(results, "Third", "https://example.com/c", max_results=2)

    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/a"
    assert results[1]["url"] == "https://example.com/b"
