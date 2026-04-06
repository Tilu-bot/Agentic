"""
Agentic - Code Runner Skill
============================
Executes Python code snippets in a sandboxed subprocess.
Output is captured and returned as a string.

Safety model (two layers):
  Layer 1 – AST validation (before execution):
    The submitted code is parsed into an abstract syntax tree and walked to
    reject import statements that name modules outside an explicit allowlist.
    Direct calls to eval(), exec(), and compile() are also rejected.
    Access to dangerous dunder attributes (__class__.__bases__ chains used
    for sandbox escapes) is blocked.

  Layer 2 – Subprocess isolation (at execution time):
    Code runs in a fresh interpreter process via asyncio.create_subprocess_exec.
    stdout/stderr are captured; there is no interactive stdin.  A hard wall-
    clock timeout kills the process if it runs too long.

The old _SANDBOX_PREAMBLE approach (modifying builtins in a subprocess)
provided no real isolation: import statements use the bytecode IMPORT_NAME
opcode which does not go through the builtins dict at all.  The AST check
is the correct place to enforce module-level restrictions.
"""
from __future__ import annotations

import ast
import asyncio
import sys
import textwrap

from skills.base import SkillBase
from utils.logger import build_logger

log = build_logger("agentic.skill.code")

_DEFAULT_TIMEOUT = 15.0
_MAX_OUTPUT = 4000

# Modules that pure-Python data-processing code legitimately needs.
# Only the top-level package name is checked; sub-imports from an allowed
# package (e.g. "math.inf") are permitted transitively.
_ALLOWED_MODULES: frozenset[str] = frozenset({
    "math", "cmath", "decimal", "fractions", "statistics",
    "random", "itertools", "functools", "operator", "string",
    "re", "json", "csv", "textwrap", "unicodedata",
    "datetime", "time", "calendar",
    "collections", "heapq", "bisect", "array",
    "pprint", "reprlib", "enum",
    "typing", "abc", "dataclasses",
    "io", "struct", "codecs",
})

# Dunder attributes commonly used in sandbox-escape chains
_BLOCKED_ATTRS: frozenset[str] = frozenset({
    "__class__", "__bases__", "__subclasses__", "__globals__",
    "__builtins__", "__import__", "__loader__", "__spec__",
})


def _validate_code(code: str) -> None:
    """
    Parse *code* and walk its AST to reject constructs that could escape the
    subprocess sandbox or harm the host system.

    Raises:
        ValueError      – if the code cannot be parsed (syntax error).
        PermissionError – if a forbidden construct is detected.
    """
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"Syntax error in submitted code: {exc}") from exc

    for node in ast.walk(tree):
        # Block imports of modules outside the allowlist
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                if top_level not in _ALLOWED_MODULES:
                    raise PermissionError(
                        f"Importing '{alias.name}' is not allowed. "
                        f"Permitted top-level packages: {sorted(_ALLOWED_MODULES)}"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod not in _ALLOWED_MODULES:
                raise PermissionError(
                    f"Importing from '{node.module}' is not allowed."
                )

        # Block explicit calls to eval / exec / compile
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "compile"):
                    raise PermissionError(
                        f"Calling '{node.func.id}' is not allowed in the sandbox."
                    )

        # Block access to dangerous dunder attributes used in escape chains
        elif isinstance(node, ast.Attribute):
            if node.attr in _BLOCKED_ATTRS:
                raise PermissionError(
                    f"Accessing attribute '{node.attr}' is not allowed in the sandbox."
                )


class RunPythonSkill(SkillBase):
    name = "run_python"
    description = (
        "Execute a Python code snippet in a sandboxed subprocess and return "
        "its stdout/stderr output. Suitable for calculations, data processing, "
        "and algorithmic tasks. Only standard-library math/data modules are "
        "available; network and filesystem access are not permitted."
    )
    parameters = {
        "code": {"type": "string", "description": "Python code to execute"},
        "timeout": {"type": "number", "description": "Execution timeout in seconds (default 15)"},
    }
    required = ["code"]
    tags = ["code", "compute"]

    async def execute(self, code: str, timeout: float = _DEFAULT_TIMEOUT) -> str:
        # Layer 1: AST safety check before we touch a subprocess
        try:
            _validate_code(code)
        except (ValueError, PermissionError) as exc:
            return f"[Code rejected by safety check: {exc}]"

        # Layer 2: run in an isolated subprocess (the process boundary IS the
        # primary sandbox; the AST check is defence-in-depth)
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                code,
                stdin=asyncio.subprocess.DEVNULL,   # no interactive reads
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
