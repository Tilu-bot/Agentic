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

import asyncio
import inspect
import io
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

try:
    import h2  # type: ignore[import-not-found]
    _HTTP2_ENABLED = True
except Exception:
    _HTTP2_ENABLED = False

_BROWSER_HEADER_PROFILES: list[dict[str, str]] = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) "
            "Gecko/20100101 Firefox/124.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
    },
]

_RETRYABLE_STATUS_CODES = {403, 408, 425, 429, 500, 502, 503, 504}
_MAX_PRIMARY_FETCH_ATTEMPTS = 2

# Very lightweight HTML stripper – no external dependency required
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE  = re.compile(r"\n{3,}")
_DDG_RESULT_RE = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_DDG_LITE_LINK_RE = re.compile(
    r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

_SEARXNG_PUBLIC_INSTANCES: list[str] = [
    "https://searx.be",
    "https://search.sapti.me",
    "https://searx.tiekoetter.com",
]


class _SimpleResponse:
    """Small response wrapper so fallback transports can mimic httpx response access."""

    def __init__(
        self,
        status_code: int,
        text: str,
        headers: dict[str, str],
        content: bytes | None = None,
    ):
        self.status_code = status_code
        self.text = text
        self.headers = headers
        self.content = content if content is not None else text.encode("utf-8", errors="ignore")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

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


def _extract_pdf_text_from_bytes(blob: bytes) -> str:
    """Best-effort PDF text extraction from raw response bytes."""
    try:
        from pypdf import PdfReader
    except Exception:
        return "PDF detected but pypdf is not installed. Install with: pip install pypdf"

    try:
        reader = PdfReader(io.BytesIO(blob))
        pages: list[str] = []
        for idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"--- Page {idx} ---\n{text}")
        return "\n\n".join(pages) if pages else "(No text could be extracted from this PDF)"
    except Exception as exc:
        return f"(Failed to parse PDF content: {exc})"


def _normalize_result_url(href: str) -> str:
    href = href.strip()
    if href.startswith("//"):
        return f"https:{href}"

    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l"):
        qs = urllib.parse.parse_qs(parsed.query)
        redirected = qs.get("uddg", [""])[0]
        if redirected:
            return urllib.parse.unquote(redirected)
    return urllib.parse.unquote(href)


def _collect_search_result(
    results: list[dict[str, str]],
    title: str,
    url: str,
    max_results: int,
) -> None:
    title = title.strip()
    url = _normalize_result_url(url)
    if not title or not url.startswith(("http://", "https://")):
        return

    for item in results:
        if item["url"] == url:
            return

    results.append({"title": title, "url": url})
    if len(results) > max_results:
        del results[max_results:]


def _iter_ddgs_text(ddgs: Any, query: str, max_results: int):
    """Try multiple call signatures across ddgs/duckduckgo_search versions."""
    for kwargs in (
        {"max_results": max_results, "backend": "lite"},
        {"max_results": max_results, "backend": "html"},
        {"max_results": max_results},
    ):
        try:
            result_iter = ddgs.text(query, **kwargs)
            if inspect.isawaitable(result_iter):
                continue
            yielded = False
            for item in result_iter:
                yielded = True
                yield item
            if yielded:
                return
        except TypeError:
            continue


async def _try_curl_cffi_fetch(url: str) -> _SimpleResponse | None:
    """
    Optional transport fallback using browser TLS fingerprints.

    Some anti-bot protections block default TLS/client fingerprints from httpx.
    curl_cffi impersonation often succeeds where plain clients get 403.
    """
    try:
        from curl_cffi import requests as curl_requests  # type: ignore[import-not-found]
    except Exception:
        return None

    def _do_fetch() -> _SimpleResponse:
        last_error: Exception | None = None
        for headers in _BROWSER_HEADER_PROFILES:
            try:
                resp = curl_requests.get(
                    url,
                    headers=headers,
                    timeout=_TIMEOUT,
                    impersonate="chrome124",
                    allow_redirects=True,
                )
                if resp.status_code in _RETRYABLE_STATUS_CODES:
                    last_error = RuntimeError(f"HTTP {resp.status_code} from {url}")
                    continue
                resp.raise_for_status()
                return _SimpleResponse(
                    resp.status_code,
                    resp.text,
                    dict(resp.headers),
                    resp.content,
                )
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Failed to fetch URL: {url}")

    try:
        return await asyncio.to_thread(_do_fetch)
    except Exception as exc:
        log.debug("curl_cffi fallback failed for %s: %s", url, exc)
        return None


async def _search_searxng(
    client: Any,
    query: str,
    max_results: int,
) -> list[dict[str, str]]:
    """Fallback search provider based on public SearXNG instances."""
    results: list[dict[str, str]] = []
    for base_url in _SEARXNG_PUBLIC_INSTANCES:
        try:
            resp = await client.get(
                f"{base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "safesearch": "0",
                    "language": "en-US",
                },
                headers=_BROWSER_HEADER_PROFILES[0],
            )
            if resp.status_code in _RETRYABLE_STATUS_CODES:
                continue
            resp.raise_for_status()
            payload = json.loads(resp.text)
            for item in payload.get("results", []):
                if not isinstance(item, dict):
                    continue
                _collect_search_result(
                    results,
                    str(item.get("title", "")),
                    str(item.get("url", "")),
                    max_results,
                )
                if len(results) >= max_results:
                    break
            if results:
                return results
        except Exception as exc:
            log.debug("SearXNG instance failed (%s): %s", base_url, exc)

    return results


async def _request_with_403_fallback(client: Any, url: str) -> Any:
    """
    Fetch URL with multiple browser-like header profiles.

    If the origin repeatedly returns 403, attempt a read-only text mirror
    fallback (`r.jina.ai`) so research flows still receive useful content.
    """
    last_error: Exception | None = None

    for attempt in range(1, _MAX_PRIMARY_FETCH_ATTEMPTS + 1):
        for headers in _BROWSER_HEADER_PROFILES:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code in _RETRYABLE_STATUS_CODES:
                    last_error = RuntimeError(f"HTTP {resp.status_code} from {url}")
                    continue
                resp.raise_for_status()
                return resp
            except Exception as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code in _RETRYABLE_STATUS_CODES:
                    last_error = exc
                    continue
                # Retry transport-layer failures (TLS, connect, timeouts) so fallback paths run.
                if status_code is None:
                    last_error = exc
                    continue
                raise

        if attempt < _MAX_PRIMARY_FETCH_ATTEMPTS:
            await asyncio.sleep(0.35 * attempt)

    curl_response = await _try_curl_cffi_fetch(url)
    if curl_response is not None:
        return curl_response

    mirror_url = f"https://r.jina.ai/{url}"
    try:
        resp = await client.get(mirror_url, headers=_BROWSER_HEADER_PROFILES[0])
        resp.raise_for_status()
        return resp
    except Exception as exc:
        if last_error is not None:
            raise RuntimeError(
                f"403 Forbidden from origin URL after retries: {url}"
            ) from last_error
        raise RuntimeError(f"Failed to fetch URL: {url}") from exc


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
            http2=_HTTP2_ENABLED,
        ) as client:
            resp = await _request_with_403_fallback(client, url)

        content_type = resp.headers.get("content-type", "").lower()
        url_path = parsed.path.lower()

        if "application/pdf" in content_type or url_path.endswith(".pdf"):
            blob = getattr(resp, "content", None)
            if not isinstance(blob, (bytes, bytearray)):
                blob = resp.text.encode("utf-8", errors="ignore")
            text = _extract_pdf_text_from_bytes(bytes(blob))
        elif "text/html" in content_type:
            text = _strip_html(resp.text)
        else:
            text = resp.text

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"
        return text


class SearchWebSkill(SkillBase):
    name = "search_web"
    description = (
        "Search the public web using open providers (DuckDuckGo + SearXNG) "
        "and return top results with title and URL. No API key required."
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
                for item in _iter_ddgs_text(ddgs, query, max_results):
                    if not isinstance(item, dict):
                        continue
                    _collect_search_result(
                        results,
                        str(item.get("title", "")),
                        str(item.get("href", "")),
                        max_results,
                    )
                    if len(results) >= max_results:
                        break
        except Exception as exc:
            log.debug("ddgs library path unavailable: %s", exc)

        if not results:
            try:
                from duckduckgo_search import DDGS  # type: ignore[import-not-found]

                with DDGS() as ddgs:
                    for item in _iter_ddgs_text(ddgs, query, max_results):
                        if not isinstance(item, dict):
                            continue
                        _collect_search_result(
                            results,
                            str(item.get("title", "")),
                            str(item.get("href", "")),
                            max_results,
                        )
                        if len(results) >= max_results:
                            break
            except Exception as exc:
                log.debug("duckduckgo_search library path unavailable: %s", exc)

        lite_url = f"https://lite.duckduckgo.com/lite/?q={encoded}"
        html_url = f"https://html.duckduckgo.com/html/?q={encoded}"

        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            http2=_HTTP2_ENABLED,
        ) as client:
            if not results:
                try:
                    lite_resp = await _request_with_403_fallback(client, lite_url)
                    lite_html = lite_resp.text
                    for href, title_html in _DDG_LITE_LINK_RE.findall(lite_html):
                        _collect_search_result(
                            results,
                            _clean_html_fragment(title_html),
                            href,
                            max_results,
                        )
                        if len(results) >= max_results:
                            break
                except Exception as exc:
                    log.debug("DuckDuckGo lite search failed: %s", exc)

            if not results:
                html_resp = await _request_with_403_fallback(client, html_url)
                html = html_resp.text

                matches = _DDG_RESULT_RE.findall(html)
                results = []
                for href, title_html in matches:
                    _collect_search_result(
                        results,
                        _clean_html_fragment(title_html),
                        href,
                        max_results,
                    )
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
                for item in self._extract_instant_answer_results(payload, max_results):
                    _collect_search_result(
                        results,
                        str(item.get("title", "")),
                        str(item.get("url", "")),
                        max_results,
                    )

            if len(results) < max_results:
                searx_results = await _search_searxng(client, query, max_results)
                for item in searx_results:
                    _collect_search_result(
                        results,
                        str(item.get("title", "")),
                        str(item.get("url", "")),
                        max_results,
                    )

        if not results:
            return f"No public web results found for query: {query}"

        wants_article_context = bool(
            re.search(r"\b(news|latest|today|breaking|update|current)\b", query, re.IGNORECASE)
        )
        snippets: list[str] = []
        if wants_article_context:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                follow_redirects=True,
                http2=_HTTP2_ENABLED,
            ) as client:
                for item in results[: min(3, len(results))]:
                    try:
                        _check_url_safe(item["url"])
                        resp = await _request_with_403_fallback(client, item["url"])
                        text = _strip_html(resp.text)
                        snippet = re.sub(r"\s+", " ", text).strip()[:500]
                        if snippet:
                            snippets.append(f"- {item['title']}\n  {item['url']}\n  Snippet: {snippet}")
                    except Exception as exc:
                        snippets.append(f"- {item['title']}\n  {item['url']}\n  Snippet unavailable: {exc}")

        lines = [f"Search results for: {query}"]
        for idx, item in enumerate(results, start=1):
            lines.append(f"{idx}. {item['title']}")
            lines.append(f"   {item['url']}")
        if snippets:
            lines.append("")
            lines.append("Article context:")
            lines.extend(snippets)
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
