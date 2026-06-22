#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bootstrap the Python environment used by scripts/start.py.

Creates (or reuses) a venv in the LMCache checkout and installs:
  - PyTorch + torchvision + torchaudio (CUDA 12.8 wheels by default)
  - vLLM (CUDA 12.9 release wheel — PyPI defaults to CUDA 13 and breaks)
  - LMCache editable install with LMCACHE_CUDA_MAJOR=12 (pulls cupy-cuda12x)
  - ninja (FlashInfer JIT during vLLM startup)

System packages still required separately:
  - redis-server  (sudo apt-get install redis-server)
  - NVIDIA driver + GPU

Example::

    export LMCACHE_REPO=~/LMCache
    python scripts/setup_gpu_env.py
    python scripts/setup_gpu_env.py --check   # verify only, no installs
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LMCACHE_REPO = Path.home() / "LMCache"
REQUIREMENTS_FILE = Path(__file__).resolve().parent / "requirements-gpu-stack.txt"

DEFAULT_VLLM_VERSION = "0.23.0"
DEFAULT_TORCH_CUDA_TAG = "cu128"
# vLLM 0.23.0 publishes cu129 + cu13 wheels on GitHub; PyPI resolves to cu13.
DEFAULT_VLLM_CUDA_TAG = "cu129"
VLLM_WHEEL_TEMPLATE = (
    "https://github.com/vllm-project/vllm/releases/download/v{version}/"
    "vllm-{version}+{cuda_tag}-cp38-abi3-manylinux_2_28_{arch}.whl"
)


class SetupError(RuntimeError):
    """Raised when bootstrap or verification fails."""


def _run(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> None:
    print(f"[setup] {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env, cwd=cwd)


def _uv_pip(python: Path, *args: str, env: dict[str, str] | None = None, cwd: Path | None = None) -> None:
    _run([_uv(), "pip", "install", "-p", str(python), *args], env=env, cwd=cwd)


def _resolve_lmcache_repo(explicit: str) -> Path:
    repo = Path(explicit or os.getenv("LMCACHE_REPO", str(DEFAULT_LMCACHE_REPO))).expanduser()
    if not (repo / "pyproject.toml").is_file():
        raise SetupError(f"LMCache checkout not found at {repo}")
    return repo


def _venv_python(repo: Path) -> Path:
    return repo / ".venv" / "bin" / "python"


def _uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        raise SetupError("uv not found on PATH. Install from https://docs.astral.sh/uv/")
    return uv


def _machine_arch() -> str:
    machine = platform.machine()
    if machine not in {"x86_64", "aarch64"}:
        raise SetupError(f"Unsupported architecture for vLLM wheel: {machine}")
    return machine


def _vllm_wheel_url(version: str, cuda_tag: str) -> str:
    return VLLM_WHEEL_TEMPLATE.format(
        version=version,
        cuda_tag=cuda_tag,
        arch=_machine_arch(),
    )


def _torch_index(cuda_tag: str) -> str:
    return f"https://download.pytorch.org/whl/{cuda_tag}"


def ensure_venv(repo: Path, *, python: str) -> Path:
    """Create the LMCache venv if missing."""
    py = _venv_python(repo)
    if py.is_file():
        return py
    _run([_uv(), "venv", "--python", python, str(repo / ".venv")])
    if not py.is_file():
        raise SetupError(f"Failed to create venv at {py.parent.parent}")
    return py


def install_stack(
    repo: Path,
    *,
    torch_cuda_tag: str,
    vllm_version: str,
    vllm_cuda_tag: str,
    skip_vllm: bool,
    skip_lmcache: bool,
) -> None:
    """Install GPU stack packages into the LMCache venv."""
    py = _venv_python(repo)
    torch_index = _torch_index(torch_cuda_tag)

    _uv_pip(
        py,
        "torch",
        "torchvision",
        "torchaudio",
        "--index-url",
        torch_index,
    )

    if not skip_vllm:
        wheel = _vllm_wheel_url(vllm_version, vllm_cuda_tag)
        _uv_pip(
            py,
            wheel,
            "--extra-index-url",
            _torch_index(vllm_cuda_tag),
            "--index-strategy",
            "unsafe-best-match",
        )
        # Re-pin torchaudio to the torch CUDA tag (vLLM deps can pull a mismatched build).
        _uv_pip(py, "torchaudio", "--index-url", torch_index)

    if not skip_lmcache:
        env = os.environ.copy()
        env["LMCACHE_CUDA_MAJOR"] = "12"
        _uv_pip(py, "-e", str(repo), "--no-build-isolation", env=env, cwd=repo)

    if REQUIREMENTS_FILE.is_file():
        _uv_pip(py, "-r", str(REQUIREMENTS_FILE))


def verify(*, python: Path, skip_vllm: bool) -> list[str]:
    """Return a list of verification errors (empty if OK)."""
    errors: list[str] = []

    def probe(code: str, label: str) -> None:
        result = subprocess.run(
            [str(python), "-c", code],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            tail = detail[-1] if detail else "unknown error"
            errors.append(f"{label}: {tail}")

    probe(
        "import lmcache; import torch; assert torch.cuda.is_available(), 'CUDA unavailable'",
        "lmcache + torch CUDA",
    )
    probe("import cupy", "cupy (LMCACHE_CUDA_MAJOR=12 LMCache install)")
    if not skip_vllm:
        if shutil.which("ninja") is None:
            errors.append("ninja not on PATH (install via setup_gpu_env.py)")
        probe("import vllm; import vllm._C", "vllm native extensions")
        probe("import torchaudio", "torchaudio")
        vllm_cli = python.parent / "vllm"
        if vllm_cli.is_file():
            result = subprocess.run(
                [str(vllm_cli), "--help"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip().splitlines()
                tail = detail[-1] if detail else "vllm --help failed"
                errors.append(f"vllm CLI: {tail}")

    if shutil.which("redis-server") is None:
        errors.append(
            "redis-server not on PATH (sudo apt-get install redis-server)"
        )

    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lmcache-repo",
        default=os.getenv("LMCACHE_REPO", str(DEFAULT_LMCACHE_REPO)),
        help="Path to LMCache checkout (default: ~/LMCache or LMCACHE_REPO)",
    )
    parser.add_argument(
        "--python",
        default=os.getenv("DEMO_PYTHON", "3.12"),
        help="Python version for the venv (default: 3.12)",
    )
    parser.add_argument(
        "--torch-cuda-tag",
        default=os.getenv("DEMO_TORCH_CUDA_TAG", DEFAULT_TORCH_CUDA_TAG),
        help=f"PyTorch wheel CUDA tag (default: {DEFAULT_TORCH_CUDA_TAG})",
    )
    parser.add_argument(
        "--vllm-version",
        default=os.getenv("DEMO_VLLM_VERSION", DEFAULT_VLLM_VERSION),
        help=f"vLLM release version (default: {DEFAULT_VLLM_VERSION})",
    )
    parser.add_argument(
        "--vllm-cuda-tag",
        default=os.getenv("DEMO_VLLM_CUDA_TAG", DEFAULT_VLLM_CUDA_TAG),
        help=f"vLLM GitHub wheel CUDA tag (default: {DEFAULT_VLLM_CUDA_TAG})",
    )
    parser.add_argument(
        "--skip-vllm",
        action="store_true",
        help="Install LMCache/torch only (matches start.py --skip-vllm)",
    )
    parser.add_argument(
        "--skip-lmcache",
        action="store_true",
        help="Skip editable LMCache reinstall",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the environment without installing packages",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        repo = _resolve_lmcache_repo(args.lmcache_repo)
    except SetupError as exc:
        print(f"[setup] error: {exc}", file=sys.stderr)
        return 1

    py = _venv_python(repo)
    if not args.check:
        try:
            py = ensure_venv(repo, python=args.python)
            install_stack(
                repo,
                torch_cuda_tag=args.torch_cuda_tag,
                vllm_version=args.vllm_version,
                vllm_cuda_tag=args.vllm_cuda_tag,
                skip_vllm=args.skip_vllm,
                skip_lmcache=args.skip_lmcache,
            )
        except (SetupError, subprocess.CalledProcessError) as exc:
            print(f"[setup] error: {exc}", file=sys.stderr)
            return 1
    elif not py.is_file():
        print(f"[setup] error: venv missing at {py.parent.parent}", file=sys.stderr)
        print("[setup] Run: python scripts/setup_gpu_env.py", file=sys.stderr)
        return 1

    errors = verify(python=py, skip_vllm=args.skip_vllm)
    if errors:
        print("[setup] environment check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "[setup] Fix with: python scripts/setup_gpu_env.py",
            file=sys.stderr,
        )
        return 1

    print(f"[setup] OK — use: export LMCACHE_PYTHON={py}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
