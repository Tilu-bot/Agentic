"""
Agentic - Cortex
================
The central reasoning unit of the Reactive Cortex Architecture (RCA).

The Cortex drives the *Deliberation Pulse* using a ReAct loop
(Reason → Act → Observe → Reason … → Final Answer):

  1. Receive user input via the Signal Lattice.
  2. Assemble context from the Memory Lattice (query-relevance ranked).
  3. Build system prompt and initial message list.
  4. Resolve tool schema (native calling for supported models).
  5. Loop up to react_max_iterations times:
       a. Stream a model response.
       b. Extract any skill-call markers from the response.
       c. If none → Final Answer.  Break.
       d. Run skill invocations in parallel via TaskFibers (Act).
       e. Build an Observation message from results (Observe).
       f. Append assistant turn + observation to message history, loop.
  6. Write final answer to the Memory Lattice.
  7. Emit DELIBERATION_END signal with the full response.

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
from model.gemma_nexus import GemmaNexus, get_assistant_role
from model.prompt_weaver import PromptWeaver, SkillInvocation
from utils.config import cfg
from utils.logger import build_logger

log = build_logger("agentic.cortex")

# Status message template emitted to the UI after each ReAct tool round-trip.
# Shows the current iteration and the names of skills that were executed.
_REACT_ITERATION_STATUS = (
    "\n\n[⚙ Skills executed: {skill_names} — reasoning continues…]\n\n"
)

# Approximate characters per token for the context-window overflow estimator.
# GPT/LLaMA family tokenizers average ~4 chars/token for English prose.
_CHARS_PER_TOKEN = 4

# Fraction of the context limit at which we warn instead of hard-stop.
# 0.85 leaves ~15 % headroom for the model's reply.
_CONTEXT_WARN_RATIO = 0.85


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
        # Input queue: replaces the old _deliberating bool so that inputs
        # submitted while deliberation is in progress are queued rather than
        # silently dropped.  _consume_inputs() drains the queue one item at a
        # time, ensuring deliberations are strictly serialised.
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._active = True
        self._thread.start()
        lattice.attach_loop(self._loop)
        # Schedule the serialised input consumer on the cortex event loop.
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self._consume_inputs())
        )
        log.info("Cortex started (thread: %s)", self._thread.name)

    def stop(self) -> None:
        self._active = False
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        log.info("Cortex stopped")

    def update_memory(self, memory: MemoryLattice) -> None:
        """Replace the active MemoryLattice (e.g. when a new session is started)."""
        self._memory = memory

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # ------------------------------------------------------------------
    # Public entry point (called from UI thread)
    # ------------------------------------------------------------------

    def submit_input(self, text: str) -> None:
        """
        Submit user input for processing.

        Puts the text onto the input queue.  If a deliberation is already in
        progress the message is held until it completes (no input is dropped).
        When more than one message is already waiting, the user is notified via
        the signal lattice so they know their message is queued.
        """
        if not text.strip():
            return
        queue_size = self._input_queue.qsize()
        if queue_size > 0:
            lattice.emit_kind(
                SigKind.NOTIFICATION,
                {"message": f"Message queued (position {queue_size + 1})."},
                source="cortex",
            )
        # put_nowait is safe: the queue is unbounded and this is a fast O(1) op.
        self._loop.call_soon_threadsafe(self._input_queue.put_nowait, text)

    # ------------------------------------------------------------------
    # Deliberation Pulse
    # ------------------------------------------------------------------

    async def _consume_inputs(self) -> None:
        """
        Serialised input consumer – runs on the Cortex event loop.

        Waits for items from *_input_queue* and runs one deliberation at a
        time.  Because this coroutine awaits ``_deliberate_inner`` before
        calling ``get()`` again, deliberations are strictly sequential and
        no input is ever dropped.  The loop exits when ``_active`` becomes
        False and a short wait elapses with no new input.
        """
        while True:
            try:
                text = await asyncio.wait_for(self._input_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if not self._active:
                    break
                continue
            try:
                await self._deliberate_inner(text)
            except Exception as exc:
                log.exception("Unhandled deliberation error: %s", exc)

    async def _deliberate_inner(self, user_text: str) -> None:
        """
        ReAct deliberation loop: Reason → Act → Observe → Reason … → Answer.

        Each iteration:
          1. Stream a model response.
          2. Extract any skill-call markers from that response.
          3. If skill calls are found → run them in parallel (Act), build an
             Observation message from the results, append both turns to the
             conversation, and loop (Reason again with new context).
          4. If no skill calls are found → this is the Final Answer.  Stop.

        The loop is bounded by ``react_max_iterations`` (default 6) to prevent
        runaway execution.  The final answer (last iteration's response) is
        written to the Memory Lattice and broadcast via DELIBERATION_END.
        """
        log.info("Deliberation pulse: '%s'", user_text[:80])

        # ── 0. Signal that deliberation has begun ────────────────────────
        lattice.emit_kind(
            SigKind.DELIBERATION_START,
            {"input": user_text[:200]},
            source="cortex",
        )

        # ── 1. Write user input to fluid memory ─────────────────────────
        self._memory.fluid_write("user", user_text)

        # ── 2. Assemble context, ranked by query relevance ───────────────
        mem_ctx = self._memory.assemble_context(
            include_crystal=5, include_bedrock=10, query=user_text
        )

        # ── 3. Build initial system prompt + message list ────────────────
        system_prompt = self._weaver.build_system(memory_context=mem_ctx)
        fluid         = self._memory.fluid_read()
        messages      = self._weaver.build_messages(fluid[:-1], user_text)

        # ── 4. Resolve tool schema for models that support native calling ─
        tools: list[dict] | None = (
            self._registry.tools_schema()
            if self._nexus.tool_calls_supported
            else None
        )

        # ── 4b. Context-window overflow check ────────────────────────────
        # Estimate the total prompt token count using a chars/token heuristic.
        # If we are approaching the model's context limit, warn in the log
        # and emit a NOTIFICATION so the user knows the context may be truncated.
        context_limit: int = cfg.get("context_limit_tokens", 4096)
        estimated_tokens = (
            sum(len(m.get("content", "")) for m in messages)
            + len(system_prompt)
        ) // _CHARS_PER_TOKEN
        if estimated_tokens > context_limit * _CONTEXT_WARN_RATIO:
            log.warning(
                "Estimated prompt size (%d tokens) exceeds %.0f%% of "
                "context limit (%d).  Oldest fluid entries may be truncated "
                "by the model.  Consider starting a new session.",
                estimated_tokens, _CONTEXT_WARN_RATIO * 100, context_limit,
            )
            lattice.emit_kind(
                SigKind.NOTIFICATION,
                {
                    "message": (
                        f"Context is nearly full (~{estimated_tokens} tokens / "
                        f"{context_limit} limit).  Older context may be lost. "
                        "Consider starting a new chat session."
                    )
                },
                source="cortex",
            )

        max_iterations = cfg.get("react_max_iterations", 6)
        final_response = ""
        total_skills_used = 0

        # ── 5. ReAct loop ────────────────────────────────────────────────
        for iteration in range(max_iterations):
            log.info(
                "ReAct iteration %d/%d for '%s'",
                iteration + 1, max_iterations, user_text[:40],
            )

            # Stream one model response
            response_parts: list[str] = []
            scan_buf = ""

            try:
                async for token in self._nexus.stream(
                    messages,
                    system=system_prompt,
                    temperature=0.7,
                    max_tokens=2048,
                    tools_schema=tools,
                ):
                    response_parts.append(token)
                    scan_buf += token

                    if self._on_token:
                        try:
                            self._on_token(token)
                        except Exception:
                            pass

            except Exception as exc:
                log.exception("Model stream failed: %s", exc)
                err_msg = f"\n[Model error: {exc}]"
                if self._on_token:
                    self._on_token(err_msg)
                response_parts.append(err_msg)

            full_response = "".join(response_parts)
            final_response = full_response

            # Extract skill calls from the entire iteration response
            skill_queue = self._weaver.extract_skill_calls(full_response)

            if not skill_queue:
                # No tool calls → final answer reached
                log.info(
                    "ReAct: no tool calls in iteration %d – final answer",
                    iteration + 1,
                )
                break

            # ── Act: run skill fibers in parallel ────────────────────────
            results = await self._run_skills(skill_queue)
            total_skills_used += len(skill_queue)

            lattice.emit_kind(
                SigKind.REACT_ITERATION,
                {
                    "iteration":   iteration + 1,
                    "skills_run":  [inv.skill_name for inv in skill_queue],
                    "result_count": len(results),
                },
                source="cortex",
            )
            log.info(
                "ReAct iteration %d: ran %d skills",
                iteration + 1, len(skill_queue),
            )

            # Notify the streaming UI that tools have been executed and the
            # model is about to continue reasoning.
            if self._on_token and iteration + 1 < max_iterations:
                skill_names = ", ".join(inv.skill_name for inv in skill_queue)
                try:
                    self._on_token(
                        _REACT_ITERATION_STATUS.format(skill_names=skill_names)
                    )
                except Exception:
                    pass

            # ── Observe: append tool call + observation to message history ─
            asst_role = get_assistant_role(cfg.get("model_id", ""))
            messages.append({"role": asst_role, "content": full_response})
            obs_text = self._weaver.format_observations(results)
            messages.append({"role": "user", "content": obs_text})

        else:
            log.warning("ReAct: reached max iterations (%d)", max_iterations)

        # Guard against a completely empty response (e.g. the model emitted
        # zero tokens and no exception was raised).  This is extremely rare
        # but we must not write an empty assistant turn to fluid memory.
        if not final_response:
            final_response = (
                "Error: the model did not generate a response. "
                "Please try again or rephrase your input."
            )
            log.warning("ReAct: final_response is empty, substituting placeholder")

        # ── 6. Write final answer to fluid memory ────────────────────────
        self._memory.fluid_write("assistant", final_response)

        # ── 7. Signal deliberation complete ──────────────────────────────
        lattice.emit_kind(
            SigKind.DELIBERATION_END,
            {"response": final_response, "skills_used": total_skills_used},
            source="cortex",
        )
        log.info(
            "Deliberation complete (%d skills, %d chars)",
            total_skills_used, len(final_response),
        )

    # ------------------------------------------------------------------
    # Skill execution primitive
    # ------------------------------------------------------------------

    async def _run_skills(
        self,
        invocations: list[SkillInvocation],
    ) -> list[tuple[SkillInvocation, str, bool]]:
        """
        Execute skill calls as parallel Task Fibers and return structured results.

        Each invocation gets its own fiber.  All fibers are enqueued and then
        run_until_empty() drives them to completion concurrently (up to
        max_concurrent from the TaskFabric configuration).

        Returns a list of ``(invocation, result_str, success)`` tuples in the
        same order as *invocations*.  This is consumed by
        ``PromptWeaver.format_observations`` to build the Observation turn for
        the next ReAct iteration.
        """
        id_to_inv: dict[str, SkillInvocation] = {}
        for inv in invocations:
            fiber = TaskFiber(
                label=f"skill:{inv.skill_name}",
                fn=self._make_skill_fn(inv),
                tags=["skill"],
            )
            fid = self._fabric.add_fiber(fiber)
            id_to_inv[fid] = inv

        await self._fabric.run_until_empty()

        results: list[tuple[SkillInvocation, str, bool]] = []
        for fid, inv in id_to_inv.items():
            fiber = self._fabric.get_fiber(fid)
            if fiber is None:
                results.append((inv, "ERROR: fiber not found", False))
                continue
            if fiber.status == FiberStatus.DONE:
                results.append((inv, str(fiber.result)[:1000], True))
            elif fiber.status == FiberStatus.FAILED:
                results.append((inv, f"ERROR: {fiber.error}", False))
            else:
                results.append(
                    (inv, f"ERROR: unexpected fiber state {fiber.status}", False)
                )
        return results

    def _make_skill_fn(self, inv: SkillInvocation):
        async def _fn(fiber: TaskFiber):
            fiber.set_progress(0.1)
            result = await self._registry.invoke(inv.skill_name, **inv.args)
            fiber.set_progress(1.0)
            if result.success:
                return result.output
            raise RuntimeError(result.error)
        return _fn
