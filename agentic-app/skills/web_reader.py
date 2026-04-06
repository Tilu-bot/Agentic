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

# Very lightweight HTML stripper – no external dependency required
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE  = re.compile(r"\n{3,}")

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


class FetchWebSkill(SkillBase):
    name = "fetch_web"
    description = (
        "Fetch and return the text content of a web page. "
        "Returns plain text (HTML stripped). Best for documentation, articles, wikis."
    )
    parameters = {
        "url": {"type": "string", "description": "Full URL to fetch (https://...)"},
        "max_chars": {"type": "integer", "description": "Max characters to return"},
    }
    required = ["url"]
    tags = ["web"]

    async def execute(self, url: str, max_chars: int = _MAX_CHARS) -> str:
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

        log.info("Fetching: %s", url)
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
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


def register_all() -> None:
    FetchWebSkill.register()
