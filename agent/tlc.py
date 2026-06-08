"""TLC runner utilities."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TLCResult:
    module: str
    passed: bool
    returncode: int
    stdout: str
    stderr: str
    error: str
    states_found: int | None = None


_STATES_RE = re.compile(r"(\d+)\s+states generated,\s+(\d+)\s+distinct states found")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def tla_tools_jar() -> Path:
    configured = os.environ.get("TLA_TOOLS_JAR", "tools/tla2tools.jar")
    path = Path(configured)
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def run_tlc(module_name: str, tla_code: str, cfg_code: str, timeout: float = 30.0) -> TLCResult:
    """Run TLC against the provided module and cfg text."""
    jar = tla_tools_jar()
    if not jar.exists():
        return TLCResult(
            module=module_name,
            passed=False,
            returncode=1,
            stdout="",
            stderr="",
            error=f"TLC jar not found: {jar}",
        )

    with tempfile.TemporaryDirectory(prefix="tla_agent_") as tmp:
        workdir = Path(tmp)
        tla_path = workdir / f"{module_name}.tla"
        cfg_path = workdir / f"{module_name}.cfg"
        tla_path.write_text(tla_code, encoding="utf-8")
        cfg_path.write_text(cfg_code, encoding="utf-8")

        try:
            proc = subprocess.run(
                ["java", "-cp", str(jar), "tlc2.TLC", "-config", cfg_path.name, tla_path.name],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return TLCResult(
                module=module_name,
                passed=False,
                returncode=124,
                stdout=stdout,
                stderr=stderr,
                error=f"TLC timed out after {timeout}s",
            )

    output = f"{proc.stdout}\n{proc.stderr}"
    match = _STATES_RE.search(output)
    states_found = int(match.group(2)) if match else None
    passed = proc.returncode == 0 and "No error has been found" in proc.stdout
    error = "" if passed else (proc.stderr.strip() or _first_error(proc.stdout) or "TLC failed")
    return TLCResult(
        module=module_name,
        passed=passed,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        error=error,
        states_found=states_found,
    )


def _first_error(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("Error:") or "Error:" in line:
            return line
    return ""
