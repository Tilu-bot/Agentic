"""
Agentic - Web Reader Skill
===========================
Fetches web page content using httpx (async).
Returns cleaned plain text; does not execute JavaScript.
"""
from __future__ import annotations

import re
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
        # Validate URL
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Only http/https URLs allowed, got: {parsed.scheme}")

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
