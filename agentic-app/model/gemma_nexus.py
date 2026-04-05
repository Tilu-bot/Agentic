"""
Agentic - Gemma Nexus
=====================
Efficient adapter for the Gemma model served via Ollama.

Features:
  • Streaming token delivery via async generators
  • Automatic retry on transient network errors
  • Token usage tracking
  • Clean separation from Cortex logic (Nexus knows nothing about tasks)

Ollama API used:
  POST /api/chat   → streaming JSON-LD response
  GET  /api/tags   → list available models
  POST /api/pull   → pull a model (used in setup)

Streaming format (NDJSON):
  {"model":"...", "message":{"role":"assistant","content":"tok"}, "done":false}
  {"model":"...", "done":true, "eval_count":42, ...}
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from core.signal_lattice import SigKind, lattice
from utils.config import cfg
from utils.logger import build_logger

log = build_logger("agentic.gemma_nexus")

_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT    = 120.0
_MAX_RETRIES     = 3
_RETRY_DELAY     = 1.5


@dataclass
class NexusResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# ---------------------------------------------------------------------------
# GemmaNexus
# ---------------------------------------------------------------------------

class GemmaNexus:
    """
    Async interface to an Ollama-hosted Gemma model.

    Usage:
        nexus = GemmaNexus()
        async for token in nexus.stream(messages):
            print(token, end="", flush=True)
    """

    def __init__(self) -> None:
        self._base = cfg.get("ollama_base_url", "http://localhost:11434").rstrip("/")
        self._model = cfg.get("gemma_model", "gemma3:4b")
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT, write=10.0, pool=5.0
                ),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Model availability
    # ------------------------------------------------------------------

    async def is_available(self) -> bool:
        """Check whether the Ollama server is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags", timeout=4.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            log.warning("list_models failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Completion – streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """
        Async generator that yields token strings as they arrive from Ollama.

        Args:
            messages:    List of {"role": "...", "content": "..."} dicts.
            system:      Optional system prompt (prepended as system message).
            temperature: Sampling temperature.
            max_tokens:  Maximum tokens to generate.
        """
        self._base = cfg.get("ollama_base_url", "http://localhost:11434").rstrip("/")
        self._model = cfg.get("gemma_model", "gemma3:4b")

        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        body = {
            "model": self._model,
            "messages": full_messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        lattice.emit_kind(
            SigKind.DELIBERATION_START,
            {"model": self._model, "message_count": len(full_messages)},
            source="gemma_nexus",
        )

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async for token in self._do_stream(body):
                    yield token
                return
            except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                if attempt < _MAX_RETRIES:
                    log.warning(
                        "Stream attempt %d failed (%s) – retrying in %.1fs",
                        attempt, exc, _RETRY_DELAY,
                    )
                    await asyncio.sleep(_RETRY_DELAY)
                else:
                    lattice.emit_kind(
                        SigKind.MODEL_ERROR,
                        {"error": str(exc)},
                        source="gemma_nexus",
                    )
                    log.error("Stream permanently failed: %s", exc)
                    raise
            except Exception as exc:
                lattice.emit_kind(
                    SigKind.MODEL_ERROR,
                    {"error": str(exc)},
                    source="gemma_nexus",
                )
                log.exception("Stream error: %s", exc)
                raise

    async def _do_stream(self, body: dict) -> AsyncIterator[str]:
        client = await self._get_client()
        token_count = 0
        accumulated = ""

        async with client.stream("POST", "/api/chat", json=body) as resp:
            resp.raise_for_status()
            async for raw_line in resp.aiter_lines():
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                content = chunk.get("message", {}).get("content", "")
                if content:
                    token_count += 1
                    accumulated += content
                    lattice.emit_kind(
                        SigKind.MODEL_STREAM_TOKEN,
                        {"token": content, "seq": token_count},
                        source="gemma_nexus",
                    )
                    yield content

                if chunk.get("done"):
                    eval_count = chunk.get("eval_count", 0)
                    prompt_eval = chunk.get("prompt_eval_count", 0)
                    lattice.emit_kind(
                        SigKind.MODEL_STREAM_DONE,
                        {
                            "completion_tokens": eval_count,
                            "prompt_tokens": prompt_eval,
                            "model": self._model,
                        },
                        source="gemma_nexus",
                    )
                    log.debug(
                        "Stream done: %d prompt + %d completion tokens",
                        prompt_eval, eval_count,
                    )
                    return

    # ------------------------------------------------------------------
    # Completion – full (non-streaming)
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> NexusResponse:
        """Collect full response as a single NexusResponse."""
        parts: list[str] = []
        async for token in self.stream(messages, system, temperature, max_tokens):
            parts.append(token)
        return NexusResponse(text="".join(parts), model=self._model)
