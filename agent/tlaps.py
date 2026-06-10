"""TLAPS runner utilities."""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TLAPSResult:
    module: str
    passed: bool
    returncode: int
    stdout: str
    stderr: str
    error: str
    obligations: int | None = None


_OBLIGATION_RE = re.compile(r"All\s+(\d+)\s+obligation(?:s)?\s+proved", re.IGNORECASE)
_FAIL_RE = re.compile(r"\b(failed|failure|error|unproved|not proved)\b", re.IGNORECASE)


def run_tlaps(module_name: str, tla_code: str, timeout: float = 60.0) -> TLAPSResult:
    """Run TLAPM against a generated TLA+ proof module.

    The default lookup order is:
    1. `TLAPM_CMD`, split as a shell-like command string.
    2. `tlapm` on the native PATH.
    3. `tlapm` inside WSL, when `wsl` is available.
    """
    with tempfile.TemporaryDirectory(prefix="tlaps_agent_") as tmp:
        workdir = Path(tmp)
        tla_path = workdir / f"{module_name}.tla"
        tla_path.write_text(tla_code, encoding="utf-8")

        command = _tlapm_command(workdir, tla_path.name)
        if command is None:
            return TLAPSResult(
                module=module_name,
                passed=False,
                returncode=1,
                stdout="",
                stderr="",
                error="TLAPM not found. Set TLAPM_CMD or install tlapm in PATH/WSL.",
            )

        try:
            proc = subprocess.run(
                command,
                cwd=workdir if command[0] != "wsl" else None,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return TLAPSResult(
                module=module_name,
                passed=False,
                returncode=124,
                stdout=stdout,
                stderr=stderr,
                error=f"TLAPS timed out after {timeout}s",
            )

    return _result_from_process(module_name, proc.returncode, proc.stdout, proc.stderr)


def _tlapm_command(workdir: Path, filename: str) -> list[str] | None:
    configured = os.environ.get("TLAPM_CMD", "").strip()
    if configured:
        return shlex.split(configured) + ["--cleanfp", "--timing", filename]

    if shutil.which("tlapm"):
        return ["tlapm", "--cleanfp", "--timing", filename]

    wsl = _wsl_command()
    if wsl and _wsl_has_tlapm(wsl):
        wsl_dir = _wsl_path(workdir)
        script = (
            "export TERM=dumb; "
            f"cd {shlex.quote(wsl_dir)} && "
            f"tlapm --cleanfp --timing {shlex.quote(filename)}"
        )
        return [wsl, "-e", "bash", "-lc", script]

    return None


def _wsl_command() -> str | None:
    if shutil.which("wsl"):
        return "wsl"
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wsl.exe"
    if system32.exists():
        return str(system32)
    return None


def _wsl_has_tlapm(wsl: str) -> bool:
    try:
        proc = subprocess.run(
            [wsl, "-e", "bash", "-lc", "command -v tlapm >/dev/null 2>&1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return proc.returncode == 0


def _wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[-1].lstrip("/")
    return f"/mnt/{drive}/{rest}"


def _result_from_process(module: str, returncode: int, stdout: str, stderr: str) -> TLAPSResult:
    output = f"{stdout}\n{stderr}"
    obligations = _obligations(output)
    passed = returncode == 0 and obligations is not None and not _has_failure(output)
    error = "" if passed else _error_summary(output, returncode)
    return TLAPSResult(
        module=module,
        passed=passed,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        error=error,
        obligations=obligations,
    )


def _obligations(output: str) -> int | None:
    matches = [int(match.group(1)) for match in _OBLIGATION_RE.finditer(output)]
    return matches[-1] if matches else None


def _has_failure(output: str) -> bool:
    filtered = "\n".join(
        line
        for line in output.splitlines()
        if "expect trouble" not in line and "screen size is bogus" not in line
    )
    return bool(_FAIL_RE.search(filtered))


def _error_summary(output: str, returncode: int) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    interesting = []
    for line in lines:
        lowered = line.lower()
        if any(word in lowered for word in ("error", "failed", "failure", "unproved", "not proved")):
            interesting.append(line)
    if interesting:
        return "\n".join(interesting[-10:])
    return "\n".join(lines[-12:]) or f"TLAPS failed with return code {returncode}"
