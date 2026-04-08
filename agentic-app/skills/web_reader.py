"""
Agentic - Web Reader Skill
===========================
Fetches web page content using httpx (async).
Returns cleaned plain text; does not execute JavaScript.

Security:
  Requests to loopback (127.0.0.0/8, ::1), link-local (169.254.0.0/16),
  and RFC-1918 private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  are blocked to prevent Server-Side Request Forgery (SSRF) attacks.  The
  check resolves the hostname before connecting so DNS rebinding is also
  mitigated for the common case.
"""
from __future__ import annotations

import json
import ipaddress
import re
import socket
import urllib.parse
from typing import Any

from skills.base import SkillBase
from utils.logger import build_logger

log = build_logger("agentic.skill.web")

_TIMEOUT = 15.0
_MAX_CHARS = 8000
_MAX_SEARCH_RESULTS = 5

# Very lightweight HTML stripper – no external dependency required
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE  = re.compile(r"\n{3,}")
_DDG_RESULT_RE = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

# Private / loopback / link-local IP networks that must never be fetched.
_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback IPv4
    ipaddress.ip_network("::1/128"),           # loopback IPv6
    ipaddress.ip_network("10.0.0.0/8"),        # RFC-1918 class A
    ipaddress.ip_network("172.16.0.0/12"),     # RFC-1918 class B
    ipaddress.ip_network("192.168.0.0/16"),    # RFC-1918 class C
    ipaddress.ip_network("169.254.0.0/16"),    # link-local / APIPA
    ipaddress.ip_network("fe80::/10"),         # link-local IPv6
    ipaddress.ip_network("fc00::/7"),          # unique-local IPv6
    ipaddress.ip_network("0.0.0.0/8"),         # "this" network
    ipaddress.ip_network("100.64.0.0/10"),     # shared address space (CGNAT)
]


def _check_url_safe(url: str) -> None:
    """
    Resolve *url*'s hostname and raise ValueError if the resolved IP falls
    in a blocked (private/loopback/link-local) network.

    This is a best-effort SSRF guard.  It does not fully prevent DNS
    rebinding (the OS may cache a different A record by the time httpx
    connects), but it eliminates the vast majority of accidental or
    low-sophistication attacks.
    """
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    # Reject raw IP literals that are obviously internal without DNS lookup
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _BLOCKED_NETWORKS:
            if addr in net:
                raise ValueError(
                    f"Requests to private/loopback addresses are not allowed ({addr})"
                )
        return
    except ValueError as exc:
        # If the error is our own block message, re-raise it
        if "not allowed" in str(exc):
            raise
        # Otherwise hostname is not a raw IP literal; continue to DNS resolution

    # Resolve and check all returned addresses
    try:
        info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname '{hostname}': {exc}") from exc

    for _fam, _type, _proto, _canon, sockaddr in info:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for net in _BLOCKED_NETWORKS:
            if addr in net:
                raise ValueError(
                    f"Hostname '{hostname}' resolves to a private/loopback address "
                    f"({addr}) which is not allowed"
                )


def _strip_html(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;",  "&", text)
    text = re.sub(r"&lt;",   "<", text)
    text = re.sub(r"&gt;",   ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = _WS_RE.sub("\n\n", text)
    return text.strip()


def _clean_html_fragment(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class FetchWebSkill(SkillBase):
    name = "fetch_web"
    description = (
        "Fetch and return the text content of a web page. "
        "Returns plain text (HTML stripped). Best for documentation, articles, wikis."
    )
    parameters = {
        "url": {"type": "string", "description": "Full URL to fetch (https://...)"},
        "max_chars": {"type": "integer", "description": "Max characters to return"},
        "allow_insecure_tls": {
            "type": "boolean",
            "description": "Disable TLS certificate verification (unsafe; default false)",
        },
    }
    required = ["url"]
    tags = ["web"]

    async def execute(
        self,
        url: str,
        max_chars: int = _MAX_CHARS,
        allow_insecure_tls: bool = False,
    ) -> str:
        # Validate URL scheme
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Only http/https URLs allowed, got: {parsed.scheme}")

        # SSRF guard: reject private/loopback destinations
        _check_url_safe(url)

        try:
            import httpx
        except ImportError:
            raise RuntimeError(
                "httpx is required for web fetching. Run: pip install httpx"
            )

        verify: Any = True
        try:
            import certifi
            verify = certifi.where()
        except Exception:
            pass
        if allow_insecure_tls:
            verify = False

        log.info("Fetching: %s", url)
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            verify=verify,
            headers={"User-Agent": "Agentic/1.0 (research assistant)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            text = _strip_html(resp.text)
        else:
            text = resp.text

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"
        return text


class SearchWebSkill(SkillBase):
    name = "search_web"
    description = (
        "Search the public web using DuckDuckGo and return top results "
        "with title and URL. No API key required."
    )
    parameters = {
        "query": {"type": "string", "description": "Search query text"},
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (1-10)",
        },
    }
    required = ["query"]
    tags = ["web"]

    async def execute(self, query: str, max_results: int = _MAX_SEARCH_RESULTS) -> str:
        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")

        max_results = max(1, min(10, int(max_results)))

        try:
            import httpx
        except ImportError:
            raise RuntimeError(
                "httpx is required for web search. Run: pip install httpx"
            )

        encoded = urllib.parse.quote_plus(query)
        log.info("DuckDuckGo search: %s", query)

        # Preferred path: open-source DDGS package (more stable
        # than scraping HTML class names that can change).
        results: list[dict[str, str]] = []
        try:
            from ddgs import DDGS  # type: ignore[import-not-found]

            with DDGS() as ddgs:
                for item in ddgs.text(query, max_results=max_results):
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("title", "")).strip()
                    url = str(item.get("href", "")).strip()
                    if title and url.startswith(("http://", "https://")):
                        results.append({"title": title, "url": url})
                    if len(results) >= max_results:
                        break
        except Exception as exc:
            log.debug("ddgs library path unavailable: %s", exc)

        if not results:
            try:
                from duckduckgo_search import DDGS  # type: ignore[import-not-found]

                with DDGS() as ddgs:
                    for item in ddgs.text(query, max_results=max_results):
                        if not isinstance(item, dict):
                            continue
                        title = str(item.get("title", "")).strip()
                        url = str(item.get("href", "")).strip()
                        if title and url.startswith(("http://", "https://")):
                            results.append({"title": title, "url": url})
                        if len(results) >= max_results:
                            break
            except Exception as exc:
                log.debug("duckduckgo_search library path unavailable: %s", exc)

        if results:
            lines = [f"Search results for: {query}"]
            for idx, item in enumerate(results, start=1):
                lines.append(f"{idx}. {item['title']}")
                lines.append(f"   {item['url']}")
            return "\n".join(lines)

        html_url = f"https://html.duckduckgo.com/html/?q={encoded}"

        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Agentic/1.0 (research assistant)"},
        ) as client:
            html_resp = await client.get(html_url)
            html_resp.raise_for_status()
            html = html_resp.text

            matches = _DDG_RESULT_RE.findall(html)
            results = []
            for href, title_html in matches:
                href = urllib.parse.unquote(href)
                title = _clean_html_fragment(title_html)
                if not href or not href.startswith(("http://", "https://")):
                    continue
                if not title:
                    continue
                results.append({"title": title, "url": href})
                if len(results) >= max_results:
                    break

            if not results:
                # Fallback: DuckDuckGo instant-answer API (open, no key)
                api_url = (
                    "https://api.duckduckgo.com/"
                    f"?q={encoded}&format=json&no_html=1&skip_disambig=1"
                )
                api_resp = await client.get(api_url)
                api_resp.raise_for_status()
                payload = json.loads(api_resp.text)
                results = self._extract_instant_answer_results(payload, max_results)

        if not results:
            return f"No public web results found for query: {query}"

        lines = [f"Search results for: {query}"]
        for idx, item in enumerate(results, start=1):
            lines.append(f"{idx}. {item['title']}")
            lines.append(f"   {item['url']}")
        return "\n".join(lines)

    @staticmethod
    def _extract_instant_answer_results(payload: dict[str, Any], max_results: int) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []

        abstract = str(payload.get("AbstractText", "")).strip()
        abstract_url = str(payload.get("AbstractURL", "")).strip()
        if abstract and abstract_url:
            results.append({"title": abstract[:140], "url": abstract_url})

        related = payload.get("RelatedTopics", [])
        if isinstance(related, list):
            for item in related:
                if len(results) >= max_results:
                    break
                if not isinstance(item, dict):
                    continue

                # Some entries are nested groups with "Topics"
                topics = item.get("Topics")
                if isinstance(topics, list):
                    for topic in topics:
                        if len(results) >= max_results:
                            break
                        if not isinstance(topic, dict):
                            continue
                        text = str(topic.get("Text", "")).strip()
                        url = str(topic.get("FirstURL", "")).strip()
                        if text and url:
                            results.append({"title": text[:140], "url": url})
                    continue

                text = str(item.get("Text", "")).strip()
                url = str(item.get("FirstURL", "")).strip()
                if text and url:
                    results.append({"title": text[:140], "url": url})

        return results[:max_results]


def register_all() -> None:
    FetchWebSkill.register()
    SearchWebSkill.register()
