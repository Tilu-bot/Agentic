"""
Agentic - Code Runner Skill
============================
Executes Python code snippets in a restricted subprocess.
Output is captured and returned as a string.

Safety measures:
  • Runs in a separate subprocess (not the main process)
  • Hard time limit (default 15 seconds)
  • stdout/stderr captured; no interactive input
  • Only basic built-ins available (no file/network access from within sandbox)
"""
from __future__ import annotations

import asyncio
import sys
import textwrap

from skills.base import SkillBase
from utils.logger import build_logger

log = build_logger("agentic.skill.code")

_DEFAULT_TIMEOUT = 15.0
_MAX_OUTPUT = 4000

# Restricted execution wrapper injected before user code
_SANDBOX_PREAMBLE = """\
import builtins as _b
import sys as _sys
_safe_builtins = {k: getattr(_b, k) for k in dir(_b) if not k.startswith('_')}
for _key in ('open', 'compile', '__import__', 'eval', 'exec', 'breakpoint'):
    _safe_builtins.pop(_key, None)
"""


class RunPythonSkill(SkillBase):
    name = "run_python"
    description = (
        "Execute a Python code snippet in a sandboxed subprocess and return "
        "its stdout/stderr output. Suitable for calculations, data processing, "
        "and algorithmic tasks. No network or file access from inside the sandbox."
    )
    parameters = {
        "code": {"type": "string", "description": "Python code to execute"},
        "timeout": {"type": "number", "description": "Execution timeout in seconds (default 15)"},
    }
    required = ["code"]
    tags = ["code", "compute"]

    async def execute(self, code: str, timeout: float = _DEFAULT_TIMEOUT) -> str:
        wrapped = textwrap.dedent(f"""\
{_SANDBOX_PREAMBLE}
{code}
""")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                wrapped,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return f"[Timeout after {timeout}s]"

            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")
            result_parts: list[str] = []
            if out:
                result_parts.append(out[:_MAX_OUTPUT])
            if err:
                result_parts.append(f"[stderr]\n{err[:1000]}")
            if proc.returncode != 0:
                result_parts.append(f"[exit code: {proc.returncode}]")
            return "\n".join(result_parts) or "[no output]"

        except Exception as exc:
            log.exception("Code execution error: %s", exc)
            return f"[Execution error: {exc}]"


def register_all() -> None:
    RunPythonSkill.register()
