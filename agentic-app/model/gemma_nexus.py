"""
Agentic - Model Nexus
=====================
Direct HuggingFace `transformers` inference for any causal instruction model.
No server, no middleware, no API keys – the model runs entirely in-process.

Model weights are downloaded once from HuggingFace Hub and cached in
~/.cache/huggingface/ (standard HF cache location).

Streaming is implemented via `TextIteratorStreamer`: model.generate() runs
in a background thread while tokens are pushed into an asyncio.Queue and
yielded to the caller one at a time, so the UI never blocks.

Race-condition fix (drain thread):
  model.generate() returns before the TextIteratorStreamer's internal queue
  is fully consumed by the drain thread.  A threading.Event (_drain_done)
  is set only once the drain loop exits; _generate() waits on this event
  before putting the None end-of-stream sentinel, so no tokens are dropped.

Supported model families (see MODEL_FAMILIES for full list):
  Gemma   – google/gemma-3-1b-it, gemma-3-4b-it, gemma-3-12b-it, …
  Llama   – meta-llama/Llama-3.2-1B-Instruct, Llama-3.1-8B-Instruct, …
  Mistral – mistralai/Mistral-7B-Instruct-v0.3
  Phi     – microsoft/Phi-4-mini-instruct, Phi-3.5-mini-instruct
  Qwen    – Qwen/Qwen2.5-1.5B-Instruct, Qwen2.5-7B-Instruct

System-role handling:
  Modern model families (Llama 3.1+, Phi-4, Qwen 2.5) support a native
  "system" role in their chat template.  Gemma and some older families do
  not; they require the system content to be embedded as a leading
  user/assistant exchange.  _supports_system_role() probes the tokenizer
  at load time and sets _system_role_supported so the right path is taken
  in stream() without wasting context tokens on the fake exchange.

Precision / dtype:
  Loading in float32 is the default but wastes ~2× the VRAM.  When a GPU is
  available, bfloat16 (on Ampere+) or float16 (on older GPUs / MPS) is used
  automatically unless 4-bit quantisation is requested.

Device selection (configured in Settings):
  "auto"  → CUDA if available, then MPS (Apple Silicon), then CPU
  "cpu"   → force CPU
  "cuda"  → force NVIDIA GPU
  "mps"   → force Apple Silicon GPU
"""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, AsyncIterator

from core.signal_lattice import SigKind, lattice
from utils.config import cfg
from utils.logger import build_logger

log = build_logger("agentic.model_nexus")

# One dedicated thread for generation so the event loop is never blocked.
_GEN_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="model-gen")

# Model families grouped for display in the Settings UI.
# Each key is a human-readable family name; the value is an ordered list of
# HuggingFace model IDs (instruction-tuned variants, lightest first).
# Dict insertion order is preserved (Python 3.7+; this project requires 3.11+)
# so the Settings quick-pick menu always shows families in the order below.
MODEL_FAMILIES: dict[str, list[str]] = {
    "Gemma": [
        "google/gemma-3-1b-it",
        "google/gemma-3-4b-it",
        "google/gemma-3-12b-it",
        "google/gemma-2-2b-it",
        "google/gemma-2-9b-it",
    ],
    "Llama": [
        "meta-llama/Llama-3.2-1B-Instruct",
        "meta-llama/Llama-3.2-3B-Instruct",
        "meta-llama/Llama-3.1-8B-Instruct",
    ],
    "Mistral": [
        "mistralai/Mistral-7B-Instruct-v0.3",
        "mistralai/Mistral-Nemo-Instruct-2407",
    ],
    "Phi": [
        "microsoft/Phi-4-mini-instruct",
        "microsoft/Phi-3.5-mini-instruct",
    ],
    "Qwen": [
        "Qwen/Qwen2.5-1.5B-Instruct",
        "Qwen/Qwen2.5-7B-Instruct",
    ],
}

# Flat list derived from MODEL_FAMILIES (used by legacy callers).
KNOWN_MODELS: list[str] = [m for models in MODEL_FAMILIES.values() for m in models]


def get_assistant_role(model_id: str) -> str:
    """
    Return the correct assistant-turn role name for a given model ID.

    Gemma instruction models use the non-standard role name ``"model"``
    instead of the conventional ``"assistant"``.  All other HuggingFace
    model families (Llama, Mistral, Phi, Qwen, …) use ``"assistant"``.
    This is passed to ``tokenizer.apply_chat_template`` so the correct
    special tokens are generated regardless of the active model.
    """
    return "model" if "gemma" in model_id.lower() else "assistant"


def _supports_tool_calls(tokenizer: Any) -> bool:
    """
    Probe whether the tokenizer's chat template supports native tool/function
    calling (Llama 3.1+, Qwen 2.5, Phi-4, Mistral-Nemo, …).

    Renders a minimal one-tool, one-user-message conversation through the
    template and checks that it succeeds without raising.  When the template
    does not know about the ``tools`` parameter it raises a Jinja2 error.

    This check runs exactly once at load time, so overhead is negligible.
    """
    try:
        tool = {
            "type": "function",
            "function": {
                "name": "probe",
                "description": "probe",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        probe_msgs = [{"role": "user", "content": "hi"}]
        tokenizer.apply_chat_template(probe_msgs, tools=[tool], tokenize=False)
        return True
    except Exception:
        return False


def _supports_system_role(tokenizer: Any) -> bool:
    """
    Probe the tokenizer's chat template for native 'system' role support.

    Renders a minimal two-message conversation (system + user) using the
    tokenizer's own Jinja2 template.  If the template raises an exception
    (e.g. because it does not know the 'system' role) we fall back to the
    fake user/assistant preamble approach.

    This check runs once at load time so the overhead is negligible.
    """
    try:
        probe = [
            {"role": "system", "content": "sys"},
            {"role": "user",   "content": "hi"},
        ]
        tokenizer.apply_chat_template(probe, tokenize=False)
        return True
    except Exception:
        return False


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
# ModelNexus
# ---------------------------------------------------------------------------

class ModelNexus:
    """
    Direct HuggingFace transformers interface for any instruction-tuned model.

    Supports Gemma, Llama, Mistral, Phi, Qwen, and any other model whose
    tokenizer ships a built-in chat_template.  The model is loaded lazily
    on first use and kept in memory for subsequent calls.  A threading.Lock
    ensures only one load runs at a time.

    Usage:
        nexus = ModelNexus()
        async for token in nexus.stream(messages):
            print(token, end="", flush=True)
    """

    def __init__(self) -> None:
        self._model_id: str = cfg.get("model_id", "google/gemma-3-1b-it")
        self._model    = None
        self._tokenizer = None
        self._load_lock = threading.Lock()
        # Set to True at load time when the tokenizer supports a native "system" role.
        # When False, the system prompt is embedded as a leading user/assistant exchange.
        self._system_role_supported: bool = False
        # Set to True at load time when the tokenizer supports native tool/function
        # calling via the apply_chat_template(tools=...) parameter.  When True,
        # the Cortex passes the tool schema directly to the model instead of
        # relying solely on the text-based @@SKILL:...@@ prompt markers.
        self._tool_calls_supported: bool = False

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load the model synchronously (called from executor thread)."""
        new_id = cfg.get("model_id", "google/gemma-3-1b-it")
        if self._model is not None and new_id == self._model_id:
            return
        with self._load_lock:
            # Re-check inside lock in case another thread loaded it first.
            if self._model is not None and new_id == self._model_id:
                return
            self._load_model(new_id)

    def _load_model(self, model_id: str) -> None:
        device_pref: str = cfg.get("device", "auto")
        quantize_4bit: bool = cfg.get("quantize_4bit", False)
        hf_token: str | None = cfg.get("hf_token", "") or None

        log.info(
            "Loading model: %s (device=%s, 4bit=%s)",
            model_id, device_pref, quantize_4bit,
        )

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "transformers and torch are required.\n"
                "Run: pip install transformers torch accelerate"
            ) from exc

        tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)

        # Probe the tokenizer once to determine if a native system role is
        # supported.  Llama 3.1+, Phi-4, Qwen 2.5 support it; Gemma does not.
        # Using the native system role avoids the fake user/assistant preamble
        # and saves significant context tokens on every request.
        system_role_ok = _supports_system_role(tokenizer)
        log.info("Model %s native system role: %s", model_id, system_role_ok)

        # Probe for native tool/function calling support (Llama 3.1+, Qwen 2.5, …)
        tool_calls_ok = _supports_tool_calls(tokenizer)
        log.info("Model %s native tool calling: %s", model_id, tool_calls_ok)

        load_kw: dict = {
            "token": hf_token,
            "low_cpu_mem_usage": True,
        }

        # Optional 4-bit quantization (requires bitsandbytes + CUDA/ROCm)
        if quantize_4bit:
            try:
                from transformers import BitsAndBytesConfig
                bnb_cfg = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                load_kw["quantization_config"] = bnb_cfg
                load_kw["device_map"] = "auto"
            except Exception as exc:
                log.warning(
                    "4-bit quantization unavailable (%s) – loading full precision", exc
                )

        # Device mapping (only set if not already set by quantization config)
        if "device_map" not in load_kw:
            if device_pref == "auto":
                if torch.cuda.is_available():
                    load_kw["device_map"] = "auto"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    load_kw["device_map"] = {"": "mps"}
                else:
                    load_kw["device_map"] = {"": "cpu"}
            else:
                load_kw["device_map"] = {"": device_pref}

        # Select a reduced-precision dtype to cut VRAM usage ~50 % vs float32.
        # bfloat16 is preferred for Ampere+ (wider dynamic range, no overflow
        # risk); float16 is used on older CUDA devices and on Apple MPS.
        # On CPU we stay in float32 because float16 is slower without hardware
        # support.  Skip when 4-bit quantisation already controls the dtype.
        if "quantization_config" not in load_kw:
            effective_device = load_kw.get("device_map", {})
            is_gpu = effective_device == "auto" or any(
                str(v) not in ("cpu", "") for v in (
                    [effective_device] if isinstance(effective_device, str)
                    else effective_device.values()
                )
            )
            if is_gpu and device_pref != "cpu":
                if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
                    load_kw["torch_dtype"] = torch.bfloat16
                else:
                    load_kw["torch_dtype"] = torch.float16

        model = AutoModelForCausalLM.from_pretrained(model_id, **load_kw)
        model.eval()

        # Swap atomically so concurrent reads are never partially-initialised
        self._tokenizer = tokenizer
        self._model     = model
        self._model_id  = model_id
        self._system_role_supported = system_role_ok
        self._tool_calls_supported  = tool_calls_ok
        log.info("Model ready: %s", model_id)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def tool_calls_supported(self) -> bool:
        """True when the loaded model's tokenizer supports native tool calling."""
        return self._tool_calls_supported

    def list_models(self) -> list[str]:
        return list(KNOWN_MODELS)

    def release(self) -> None:
        """Free model from memory (e.g. before loading a different one)."""
        self._model     = None
        self._tokenizer = None
        log.info("ModelNexus: model released")

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools_schema: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """
        Async generator yielding generated token strings one at a time.

        model.generate() runs in a dedicated ThreadPoolExecutor so the
        asyncio event loop is never blocked.  Tokens travel from the
        generation thread to the async caller via an asyncio.Queue.

        Args:
            messages:     List of {"role": "...", "content": "..."} dicts.
            system:       System prompt text (prepended to conversation).
            temperature:  Sampling temperature (0 = greedy decode).
            max_tokens:   Maximum new tokens to generate.
            tools_schema: Optional OpenAI-format tool schema list.  When the
                          loaded model's tokenizer supports native tool calling
                          (detected at load time) and this list is non-empty,
                          it is passed as ``tools=`` to ``apply_chat_template``
                          so the model produces structured tool-call output.
        """
        # Force a reload if the user changed the model in Settings.
        if cfg.get("model_id", "google/gemma-3-1b-it") != self._model_id:
            self._model = None

        loop = asyncio.get_running_loop()

        # Load model in executor (heavy on first call only).
        await loop.run_in_executor(_GEN_EXECUTOR, self._ensure_loaded)

        try:
            import torch
            from transformers import TextIteratorStreamer
        except ImportError as exc:
            raise RuntimeError(
                "transformers is required. Run: pip install transformers torch accelerate"
            ) from exc

        # Build conversation using the model's chat template.
        # When the tokenizer supports a native "system" role (detected at load
        # time) we use it directly – this is more efficient and semantically
        # correct.  For models that only support "user"/"assistant" (Gemma,
        # some older checkpoints) we embed the system content as a leading
        # user/assistant exchange so apply_chat_template() works correctly.
        asst_role = get_assistant_role(self._model_id)
        full_messages: list[dict] = []
        if system:
            if self._system_role_supported:
                full_messages.append({"role": "system", "content": system})
            else:
                full_messages.append({"role": "user",     "content": system})
                full_messages.append({"role": asst_role,  "content": "Understood."})
        full_messages.extend(messages)

        tokenizer = self._tokenizer
        model     = self._model

        input_ids = tokenizer.apply_chat_template(
            full_messages,
            add_generation_prompt=True,
            return_tensors="pt",
            **({"tools": tools_schema}
               if tools_schema and self._tool_calls_supported
               else {}),
        )

        device     = next(model.parameters()).device
        input_ids  = input_ids.to(device)
        prompt_len = int(input_ids.shape[1])

        streamer = TextIteratorStreamer(
            tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        gen_kwargs: dict = {
            "input_ids": input_ids,
            "streamer": streamer,
            "max_new_tokens": max_tokens,
            "do_sample": temperature > 0.0,
            "temperature": max(float(temperature), 1e-6),
            "repetition_penalty": 1.1,
        }

        lattice.emit_kind(
            SigKind.DELIBERATION_START,
            {"model": self._model_id, "message_count": len(full_messages)},
            source="model_nexus",
        )

        # Thread-safe queue bridges the generation thread and this coroutine.
        # None is the end-of-stream sentinel.
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()
        gen_errors: list[Exception] = []
        # _drain_done signals that _drain_streamer has finished consuming all
        # tokens from the streamer before we put the None sentinel.  Without
        # this event, model.generate() can return and _generate() can put None
        # into the queue before _drain_streamer emits the very last tokens,
        # causing those final tokens to be silently dropped.
        _drain_done = threading.Event()

        def _generate() -> None:
            try:
                with torch.no_grad():
                    model.generate(**gen_kwargs)
                # Wait up to 10 s for the drain thread to finish flushing.
                # In normal operation this completes in milliseconds.
                _drain_done.wait(timeout=10.0)
            except Exception as exc:
                gen_errors.append(exc)
            finally:
                loop.call_soon_threadsafe(token_queue.put_nowait, None)

        def _drain_streamer() -> None:
            seq = 0
            for text in streamer:
                if text:
                    seq += 1
                    lattice.emit_kind(
                        SigKind.MODEL_STREAM_TOKEN,
                        {"token": text, "seq": seq},
                        source="model_nexus",
                    )
                    loop.call_soon_threadsafe(token_queue.put_nowait, text)
            # Signal that the drain is complete so _generate() can put None.
            _drain_done.set()

        gen_thread   = threading.Thread(target=_generate,       daemon=True)
        drain_thread = threading.Thread(target=_drain_streamer, daemon=True)
        gen_thread.start()
        drain_thread.start()

        completion_tokens = 0
        try:
            while True:
                token = await token_queue.get()
                if token is None:
                    break
                completion_tokens += 1
                yield token
        finally:
            if gen_errors:
                err = gen_errors[0]
                lattice.emit_kind(
                    SigKind.MODEL_ERROR,
                    {"error": str(err)},
                    source="model_nexus",
                )
                log.exception("Generation failed: %s", err)
                raise RuntimeError(str(err)) from err

            lattice.emit_kind(
                SigKind.MODEL_STREAM_DONE,
                {
                    "completion_tokens": completion_tokens,
                    "prompt_tokens": prompt_len,
                    "model": self._model_id,
                },
                source="model_nexus",
            )
            log.debug(
                "Stream done: %d prompt + %d completion tokens",
                prompt_len, completion_tokens,
            )

    # ------------------------------------------------------------------
    # Full (non-streaming) completion
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[dict],
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools_schema: list[dict] | None = None,
    ) -> NexusResponse:
        """Collect the full response as a single NexusResponse."""
        parts: list[str] = []
        async for token in self.stream(
            messages, system, temperature, max_tokens, tools_schema
        ):
            parts.append(token)
        return NexusResponse(text="".join(parts), model=self._model_id)

    # Alias kept for API compatibility with Cortex.stop()
    async def close(self) -> None:
        self.release()


# ---------------------------------------------------------------------------
# Backward-compatibility alias
# ---------------------------------------------------------------------------

# Code that imports `GemmaNexus` directly (e.g. core/cortex.py) continues
# to work without modification.  New code should use `ModelNexus`.
GemmaNexus = ModelNexus
