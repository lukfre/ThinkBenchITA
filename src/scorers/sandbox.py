"""Run untrusted Python in a bubblewrap sandbox.

Model-written code runs with: no network, no access to the home directory or
the repo, a read-only view of the system and of the Python environment, a
private writable /work (tmpfs-backed temp dir, deleted afterwards), a wall-clock
timeout and memory / file-size / process limits. Nothing is run outside it:
if bwrap is missing, scoring fails instead of falling back to the host.
"""

import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Limits:
    timeout: float = 30.0  # wall clock, seconds, for the whole run
    memory_mb: int = 4096
    file_mb: int = 64


@dataclass
class Run:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    outputs: dict  # name -> content of the files asked back from /work (missing ones are absent)


def available() -> bool:
    return shutil.which("bwrap") is not None


def _command(workdir: Path) -> list[str]:
    cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv"]
    cmd += ["--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/bin", "/bin"]
    if Path("/usr/lib64").exists():
        cmd += ["--symlink", "usr/lib64", "/lib64"]
    cmd += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    # the interpreter and the venv's packages (numpy for the EvalPlus tests), read-only; after the
    # empty /tmp, so a checkout or interpreter under /tmp stays visible
    for path in {sys.base_prefix, sys.prefix}:
        if not path.startswith("/usr"):
            cmd += ["--ro-bind", path, path]
    cmd += ["--bind", str(workdir), "/work", "--chdir", "/work"]
    cmd += ["--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/work", "--setenv", "PYTHONDONTWRITEBYTECODE", "1"]
    cmd += ["--setenv", "PYTHONHASHSEED", "0", "--setenv", "OMP_NUM_THREADS", "1", "--setenv", "OPENBLAS_NUM_THREADS", "1"]
    return cmd


def run_python(
    files: dict[str, str | bytes],
    entry: str,
    limits: Limits = Limits(),
    stdin: str | None = None,
    collect: tuple[str, ...] = (),
) -> Run:
    """Write `files` into a fresh /work, run `python entry` there, read back `collect`."""
    if not available():
        raise RuntimeError("bubblewrap (bwrap) is not installed: refusing to run model-written code unsandboxed")

    def set_limits():
        mem = limits.memory_mb * 2**20
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_mb * 2**20,) * 2)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    with tempfile.TemporaryDirectory(prefix="evalbench-sandbox-") as tmp:
        work = Path(tmp)
        for name, content in files.items():
            mode = "wb" if isinstance(content, bytes) else "w"
            with open(work / name, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as f:
                f.write(content)
        proc = subprocess.Popen(
            _command(work) + [sys.executable, "-I", entry],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=set_limits,
            start_new_session=True,
        )
        try:
            out, err = proc.communicate(stdin.encode() if stdin is not None else None, timeout=limits.timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
            timed_out = True
        outputs = {}
        for name in collect:
            path = work / name
            # the sandboxed code owns /work: never follow a link it may have left there
            if path.is_file() and not path.is_symlink() and path.stat().st_size < 2**20:
                outputs[name] = path.read_text(encoding="utf-8", errors="replace")
        return Run(
            None if timed_out else proc.returncode,
            out.decode("utf-8", "replace")[-20000:],
            err.decode("utf-8", "replace")[-4000:],
            timed_out,
            outputs,
        )
