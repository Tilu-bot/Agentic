"""
Agentic - Cortex
================
The central reasoning unit of the Reactive Cortex Architecture (RCA).

The Cortex drives the *Deliberation Pulse*:
  1. Receive user input via the Signal Lattice.
  2. Assemble context from the Memory Lattice.
  3. Call GemmaNexus to stream a response.
  4. While streaming, watch for @@SKILL:...@@ markers.
  5. Dispatch skill invocations to SkillRegistry via TaskFibers.
  6. Inject skill results back into the response stream.
  7. Write the completed exchange to the Memory Lattice.
  8. Emit DELIBERATION_END signal with the full response.

Thread model:
  The Cortex runs its async event loop in a dedicated background thread.
  UI interaction happens via Signal Lattice callbacks only – the Cortex
  never touches tkinter widgets directly.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Callable

from core.memory_lattice import MemoryLattice
from core.signal_lattice import SigKind, Signal, lattice
from core.skill_registry import SkillRegistry
from core.task_fabric import FiberStatus, TaskFabric, TaskFiber
from model.gemma_nexus import GemmaNexus
from model.prompt_weaver import PromptWeaver, SkillInvocation
from utils.config import cfg
from utils.logger import build_logger

log = build_logger("agentic.cortex")

# How many characters to buffer before scanning for skill markers
_SCAN_BUFFER_CHARS = 50


class Cortex:
    """
    The reasoning core of Agentic.

    One Cortex instance per application session.  Its async loop runs in
    a background thread and communicates with the UI only via signals.
    """

    def __init__(
        self,
        memory: MemoryLattice,
        registry: SkillRegistry,
        on_token: Callable[[str], None] | None = None,
    ) -> None:
        self._memory   = memory
        self._registry = registry
        self._fabric   = TaskFabric(
            max_concurrent=cfg.get("max_parallel_tasks", 4)
        )
        self._nexus    = GemmaNexus()
        self._weaver   = PromptWeaver(registry.tools_manifest())

        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="cortex-loop"
        )
        self._on_token = on_token   # optional direct callback for UI streaming
        self._active   = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._active = True
        self._thread.start()
        lattice.attach_loop(self._loop)
        log.info("Cortex started (thread: %s)", self._thread.name)

    def stop(self) -> None:
        self._active = False
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        log.info("Cortex stopped")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # ------------------------------------------------------------------
    # Public entry point (called from UI thread)
    # ------------------------------------------------------------------

    def submit_input(self, text: str) -> None:
        """
        Submit user input for processing.
        Schedules a deliberation pulse on the Cortex event loop.
        """
        if not text.strip():
            return
        asyncio.run_coroutine_threadsafe(self._deliberate(text), self._loop)

    # ------------------------------------------------------------------
    # Deliberation Pulse
    # ------------------------------------------------------------------

    async def _deliberate(self, user_text: str) -> None:
        """Core cognitive cycle: perceive → reason → act → integrate."""
        log.info("Deliberation pulse: '%s'", user_text[:80])

        # 1. Write user input to fluid memory
        self._memory.fluid_write("user", user_text)

        # 2. Assemble context from memory tiers
        mem_ctx = self._memory.assemble_context(
            include_crystal=5, include_bedrock=10
        )

        # 3. Build system prompt and message list
        system_prompt = self._weaver.build_system(memory_context=mem_ctx)
        fluid         = self._memory.fluid_read()
        messages      = self._weaver.build_messages(fluid[:-1], user_text)

        # 4. Stream response from Gemma
        response_parts: list[str] = []
        skill_queue: list[SkillInvocation] = []
        scan_buf = ""

        try:
            async for token in self._nexus.stream(
                messages,
                system=system_prompt,
                temperature=0.7,
                max_tokens=2048,
            ):
                response_parts.append(token)
                scan_buf += token

                # Stream token to UI
                if self._on_token:
                    try:
                        self._on_token(token)
                    except Exception:
                        pass

                # Scan accumulated buffer for skill calls
                if len(scan_buf) >= _SCAN_BUFFER_CHARS:
                    calls = self._weaver.extract_skill_calls(scan_buf)
                    skill_queue.extend(calls)
                    scan_buf = ""

        except Exception as exc:
            log.exception("Model stream failed: %s", exc)
            err_msg = f"\n[Model error: {exc}]"
            if self._on_token:
                self._on_token(err_msg)
            response_parts.append(err_msg)

        # Check remainder of buffer
        if scan_buf:
            calls = self._weaver.extract_skill_calls(scan_buf)
            skill_queue.extend(calls)

        full_response = "".join(response_parts)

        # 5. Execute skill invocations as Task Fibers
        if skill_queue:
            full_response = await self._dispatch_skills(
                skill_queue, full_response
            )

        # 6. Write assistant response to fluid memory
        self._memory.fluid_write("assistant", full_response)

        # 7. Signal completion
        lattice.emit_kind(
            SigKind.DELIBERATION_END,
            {"response": full_response, "skills_used": len(skill_queue)},
            source="cortex",
        )
        log.info(
            "Deliberation complete (%d skills, %d chars)",
            len(skill_queue), len(full_response),
        )

    # ------------------------------------------------------------------
    # Skill dispatch
    # ------------------------------------------------------------------

    async def _dispatch_skills(
        self,
        invocations: list[SkillInvocation],
        response: str,
    ) -> str:
        """Execute skill calls and inject results into the response."""
        for inv in invocations:
            fiber = TaskFiber(
                label=f"skill:{inv.skill_name}",
                fn=self._make_skill_fn(inv),
                tags=["skill"],
            )
            self._fabric.add_fiber(fiber)

        await self._fabric.run_until_empty()

        for inv in invocations:
            # Find the fiber for this invocation
            for fiber in self._fabric.all_fibers():
                if fiber.label == f"skill:{inv.skill_name}":
                    if fiber.status == FiberStatus.DONE:
                        result_str = str(fiber.result)[:1000]
                        response = self._weaver.inject_skill_result(
                            response, inv, result_str
                        )
                    elif fiber.status == FiberStatus.FAILED:
                        response = self._weaver.inject_skill_result(
                            response, inv, f"ERROR: {fiber.error}"
                        )

        return response

    def _make_skill_fn(self, inv: SkillInvocation):
        async def _fn(fiber: TaskFiber):
            fiber.set_progress(0.1)
            result = await self._registry.invoke(inv.skill_name, **inv.args)
            fiber.set_progress(1.0)
            if result.success:
                return result.output
            raise RuntimeError(result.error)
        return _fn
