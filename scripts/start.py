#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Launch the GPU-side LMCache demo stack in separate processes.

Starts Redis, LMCache MP (with RESP L2 adapter), the LMCache controller,
the KV service gateway, and vLLM. Intended for a single-GPU machine that Hostess
reaches via cloudflared tunnels to the KV service and vLLM ports.

Example::

    export LMCACHE_PYTHON=/path/to/LMCache/.venv/bin/python
    python scripts/start.py

Environment variables (all optional):

    LMCACHE_PYTHON          Python interpreter with lmcache + vllm installed
    LMCACHE_REPO            LMCache checkout (used to find .venv/bin/python)
    DEMO_BIND_HOST          Host to bind services (default: 127.0.0.1)
    DEMO_REDIS_PORT         Redis port (default: 6379)
    DEMO_REDIS_SERVER       redis-server binary (default: redis-server on PATH)
    DEMO_LMCACHE_MP_PORT    MP ZMQ port (default: 6555)
    DEMO_LMCACHE_HTTP_PORT  MP HTTP / runtime events port (default: 8080)
    DEMO_CONTROLLER_PORT    Controller API port (default: 9000)
    DEMO_KV_SERVICE_PORT    KV service gateway port (default: 8088)
    DEMO_VLLM_PORT          vLLM OpenAI API port (default: 8000)
    DEMO_VLLM_MODEL         HuggingFace model id (default: Qwen/Qwen2.5-1.5B-Instruct)
    DEMO_L1_SIZE_GB         LMCache L1 CPU cache size (default: 32)
    DEMO_LOG_DIR            Directory for service logs (default: .logs)
    DEMO_KV_SQLITE_PATH     KV service catalog path (default: /tmp/lmcache-kv-service.sqlite3)
    HF_HOME                 Passed through to model download cache

Bootstrap Python deps (once per machine / after LMCache updates)::

    python scripts/setup_gpu_env.py

Verify deps without installing::

    python scripts/start.py --check-deps
"""

from __future__ import annotations

# Standard
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
SETUP_GPU_ENV = SCRIPTS_DIR / "setup_gpu_env.py"
DEFAULT_LMCACHE_REPO = Path.home() / "LMCache"


@dataclass(frozen=True, slots=True)
class DemoStackConfig:
    """Runtime configuration for the GPU demo stack."""

    bind_host: str
    redis_port: int
    redis_server: str
    lmcache_python: Path
    lmcache_mp_port: int
    lmcache_http_port: int
    controller_port: int
    kv_service_port: int
    vllm_port: int
    vllm_model: str
    l1_size_gb: int
    log_dir: Path
    kv_sqlite_path: Path
    skip_vllm: bool
    dry_run: bool


@dataclass(slots=True)
class ManagedService:
    """A subprocess started by the demo launcher."""

    name: str
    command: list[str]
    env: dict[str, str]
    log_path: Path
    process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        """Spawn the service process and attach logs."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = self.log_path.open("a", encoding="utf-8")
        log_handle.write(
            f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
        )
        log_handle.write(" ".join(_shell_quote(part) for part in self.command))
        log_handle.write("\n")
        log_handle.flush()
        self.process = subprocess.Popen(
            self.command,
            env=self.env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
        print(
            f"[start.py] {self.name}: pid={self.process.pid} "
            f"log={self.log_path}"
        )

    def terminate(self, timeout_seconds: float = 15.0) -> None:
        """Send SIGTERM to the process group, then SIGKILL if needed."""
        if self.process is None:
            return
        if self.process.poll() is not None:
            return
        pgid = os.getpgid(self.process.pid)
        os.killpg(pgid, signal.SIGTERM)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                return
            time.sleep(0.2)
        os.killpg(pgid, signal.SIGKILL)
        self.process.wait(timeout=5)


def _shell_quote(value: str) -> str:
    if value and all(ch not in value for ch in " \t\n\"'$\\"):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _resolve_lmcache_python(explicit: str) -> Path:
    if explicit.strip():
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"LMCACHE_PYTHON not found: {path}")
        return path

    repo_raw = os.getenv("LMCACHE_REPO", str(DEFAULT_LMCACHE_REPO)).strip()
    repo_venv = Path(repo_raw).expanduser() / ".venv" / "bin" / "python"
    if repo_venv.is_file():
        return repo_venv

    discovered = shutil.which("lmcache")
    if discovered:
        candidate = Path(discovered).resolve().parent.parent / "bin" / "python"
        if candidate.is_file():
            return candidate

    if shutil.which(sys.executable):
        probe = subprocess.run(
            [sys.executable, "-c", "import lmcache.v1.kv_service.app"],
            check=False,
            capture_output=True,
        )
        if probe.returncode == 0:
            return Path(sys.executable)

    raise FileNotFoundError(
        "Could not find a Python with LMCache installed. Set LMCACHE_PYTHON "
        "or LMCACHE_REPO to your LMCache checkout."
    )


def load_config(args: argparse.Namespace) -> DemoStackConfig:
    """Build stack configuration from CLI flags and environment variables."""
    redis_server = os.getenv("DEMO_REDIS_SERVER", "redis-server").strip()
    if not args.dry_run and not shutil.which(redis_server):
        raise FileNotFoundError(
            f"{redis_server} not found on PATH. Install Redis or set "
            "DEMO_REDIS_SERVER."
        )

    log_dir = Path(os.getenv("DEMO_LOG_DIR", str(REPO_ROOT / ".logs"))).expanduser()
    kv_sqlite = Path(
        os.getenv("DEMO_KV_SQLITE_PATH", "/tmp/lmcache-kv-service.sqlite3")
    ).expanduser()

    return DemoStackConfig(
        bind_host=os.getenv("DEMO_BIND_HOST", "127.0.0.1").strip(),
        redis_port=_env_int("DEMO_REDIS_PORT", 6379),
        redis_server=redis_server,
        lmcache_python=_resolve_lmcache_python(
            os.getenv("LMCACHE_PYTHON", "").strip()
        ),
        lmcache_mp_port=_env_int("DEMO_LMCACHE_MP_PORT", 6555),
        lmcache_http_port=_env_int("DEMO_LMCACHE_HTTP_PORT", 8080),
        controller_port=_env_int("DEMO_CONTROLLER_PORT", 9000),
        kv_service_port=_env_int("DEMO_KV_SERVICE_PORT", 8088),
        vllm_port=_env_int("DEMO_VLLM_PORT", 8000),
        vllm_model=os.getenv(
            "DEMO_VLLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"
        ).strip(),
        l1_size_gb=_env_int("DEMO_L1_SIZE_GB", 32),
        log_dir=log_dir,
        kv_sqlite_path=kv_sqlite,
        skip_vllm=args.skip_vllm,
        dry_run=args.dry_run,
    )


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def _ensure_port_free(host: str, port: int, *, label: str) -> None:
    """Fail fast when a stale process still owns a demo port."""
    if not _port_is_open(host, port):
        return
    raise RuntimeError(
        f"{label} port {host}:{port} is already in use "
        "(often an orphaned process from a prior start.py run). "
        "Free it before restarting, e.g.:\n"
        f"  ss -ltnp | grep ':{port} '\n"
        f"  pkill -f '{label}'   # or kill the PID shown by ss"
    )


def run_dependency_check(*, skip_vllm: bool) -> int:
    """Verify GPU stack dependencies via scripts/setup_gpu_env.py --check."""
    if not SETUP_GPU_ENV.is_file():
        print(
            f"[start.py] error: missing dependency helper {SETUP_GPU_ENV}",
            file=sys.stderr,
        )
        return 1
    cmd = [sys.executable, str(SETUP_GPU_ENV), "--check"]
    if skip_vllm:
        cmd.append("--skip-vllm")
    return subprocess.run(cmd, check=False).returncode


def wait_for_port(
    host: str,
    port: int,
    *,
    timeout_seconds: float,
    label: str,
) -> None:
    """Block until ``host:port`` accepts TCP connections."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _port_is_open(host, port):
            print(f"[start.py] {label} ready on {host}:{port}")
            return
        time.sleep(0.5)
    raise TimeoutError(f"{label} did not become ready on {host}:{port}")


def _base_env(config: DemoStackConfig) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _venv_binary(python: Path, name: str) -> Path | None:
    candidate = python.parent / name
    if candidate.is_file():
        return candidate
    return None


def _l2_adapter_json(config: DemoStackConfig) -> str:
    payload = {
        "type": "resp",
        "host": config.bind_host,
        "port": config.redis_port,
        "num_workers": 8,
        "serde": {"type": "fp8"},
        "eviction": {
            "eviction_policy": "LRU",
            "trigger_watermark": 0.8,
            "eviction_ratio": 0.2,
        },
    }
    return json.dumps(payload, separators=(",", ":"))


def _kv_transfer_config(config: DemoStackConfig) -> str:
    payload = {
        "kv_connector": "LMCacheMPConnector",
        "kv_role": "kv_both",
        "kv_connector_extra_config": {
            "lmcache.mp.host": f"tcp://{config.bind_host}",
            "lmcache.mp.port": config.lmcache_mp_port,
        },
    }
    return json.dumps(payload, separators=(",", ":"))


def build_services(config: DemoStackConfig) -> list[ManagedService]:
    """Return managed service definitions in startup order."""
    python = str(config.lmcache_python)
    lmcache_cli = _venv_binary(config.lmcache_python, "lmcache")
    host = config.bind_host
    base_env = _base_env(config)
    services: list[ManagedService] = []

    mp_command: list[str]
    if lmcache_cli is not None:
        mp_command = [str(lmcache_cli), "server"]
    else:
        mp_command = [python, "-m", "lmcache.cli.main", "server"]
    mp_command.extend(
        [
            "--host",
            host,
            "--port",
            str(config.lmcache_mp_port),
            "--http-host",
            host,
            "--http-port",
            str(config.lmcache_http_port),
            "--l1-size-gb",
            str(config.l1_size_gb),
            "--eviction-policy",
            "LRU",
            "--max-workers",
            "1",
            "--l2-adapter",
            _l2_adapter_json(config),
        ]
    )

    services.append(
        ManagedService(
            name="redis",
            command=[
                config.redis_server,
                "--bind",
                host,
                "--port",
                str(config.redis_port),
                "--protected-mode",
                "no",
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            env=base_env,
            log_path=config.log_dir / "redis.log",
        )
    )

    services.append(
        ManagedService(
            name="lmcache-mp",
            command=mp_command,
            env=base_env,
            log_path=config.log_dir / "lmcache-mp.log",
        )
    )

    services.append(
        ManagedService(
            name="lmcache-controller",
            command=[
                python,
                "-m",
                "lmcache.v1.api_server.__main__",
                "--host",
                host,
                "--port",
                str(config.controller_port),
            ],
            env=base_env,
            log_path=config.log_dir / "lmcache-controller.log",
        )
    )

    kv_env = base_env.copy()
    kv_env.update(
        {
            "LMCACHE_KV_SERVICE_CONTROLLER_URL": (
                f"http://{host}:{config.controller_port}"
            ),
            "LMCACHE_KV_SERVICE_RUNTIME_URL": (
                f"http://{host}:{config.lmcache_http_port}"
            ),
            "LMCACHE_KV_SERVICE_SQLITE_PATH": str(config.kv_sqlite_path),
            "LMCACHE_KV_SERVICE_TOKENIZER_MODE": "simple",
        }
    )
    services.append(
        ManagedService(
            name="kv-service",
            command=[
                python,
                "-m",
                "uvicorn",
                "lmcache.v1.kv_service.app:create_app",
                "--factory",
                "--host",
                host,
                "--port",
                str(config.kv_service_port),
            ],
            env=kv_env,
            log_path=config.log_dir / "kv-service.log",
        )
    )

    if not config.skip_vllm:
        vllm_env = base_env.copy()
        vllm_env["PYTHONHASHSEED"] = "0"
        vllm_cli = _venv_binary(config.lmcache_python, "vllm")
        if vllm_cli is not None:
            vllm_command = [
                str(vllm_cli),
                "serve",
                config.vllm_model,
            ]
        else:
            vllm_command = [
                python,
                "-m",
                "vllm.entrypoints.openai.api_server",
                "--model",
                config.vllm_model,
            ]
        vllm_command.extend(
            [
                "--host",
                host,
                "--port",
                str(config.vllm_port),
                "--gpu-memory-utilization",
                "0.80",
                "--max-model-len",
                "8192",
                "--no-enable-prefix-caching",
                "--kv-transfer-config",
                _kv_transfer_config(config),
            ]
        )
        services.append(
            ManagedService(
                name="vllm",
                command=vllm_command,
                env=vllm_env,
                log_path=config.log_dir / "vllm.log",
            )
        )

    return services


def _print_plan(config: DemoStackConfig, services: Sequence[ManagedService]) -> None:
    print("[start.py] Planned commands:")
    for service in services:
        print(f"  {service.name}:")
        print(f"    {' '.join(_shell_quote(part) for part in service.command)}")
        print(f"    log -> {service.log_path}")
    print()
    print("[start.py] Hostess / demo API should point at:")
    print(f"  LMCACHE_KV_SERVICE_URL=http://<public-host>:{config.kv_service_port}")
    print(f"  VLLM_BASE_URL=http://<public-host>:{config.vllm_port}")


def _startup_waits(
    config: DemoStackConfig,
    services: Sequence[ManagedService],
) -> list[tuple[str, Callable[[], None]]]:
    waits: list[tuple[str, Callable[[], None]]] = [
        (
            "redis",
            lambda: wait_for_port(
                config.bind_host,
                config.redis_port,
                timeout_seconds=30,
                label="redis",
            ),
        ),
        (
            "lmcache-mp",
            lambda: wait_for_port(
                config.bind_host,
                config.lmcache_http_port,
                timeout_seconds=120,
                label="lmcache-mp-http",
            ),
        ),
        (
            "lmcache-controller",
            lambda: wait_for_port(
                config.bind_host,
                config.controller_port,
                timeout_seconds=60,
                label="lmcache-controller",
            ),
        ),
        (
            "kv-service",
            lambda: wait_for_port(
                config.bind_host,
                config.kv_service_port,
                timeout_seconds=60,
                label="kv-service",
            ),
        ),
    ]
    if not config.skip_vllm:
        waits.append(
            (
                "vllm",
                lambda: wait_for_port(
                    config.bind_host,
                    config.vllm_port,
                    timeout_seconds=600,
                    label="vllm",
                ),
            )
        )
    return waits


def run_stack(config: DemoStackConfig) -> int:
    """Start all services and block until interrupted."""
    services = build_services(config)
    if config.dry_run:
        _print_plan(config, services)
        return 0

    try:
        _ensure_port_free(
            config.bind_host,
            config.redis_port,
            label="redis-server",
        )
    except RuntimeError as exc:
        print(f"[start.py] error: {exc}", file=sys.stderr)
        return 1

    _print_plan(config, services)
    waits = _startup_waits(config, services)
    wait_index = 0

    shutting_down = False

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        print(f"\n[start.py] received signal {signum}, stopping services...")
        for service in reversed(services):
            service.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    for service in services:
        service.start()
        if wait_index < len(waits) and waits[wait_index][0] == service.name:
            waits[wait_index][1]()
            wait_index += 1

    print("[start.py] all services started; press Ctrl+C to stop")
    while True:
        for service in services:
            if service.process is not None and service.process.poll() is not None:
                code = service.process.returncode
                print(
                    f"[start.py] {service.name} exited with code {code}; "
                    f"see {service.log_path}"
                )
                for other in reversed(services):
                    other.terminate()
                return code if code is not None else 1
        time.sleep(1.0)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Start Redis, LMCache MP, controller, KV service, and vLLM."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned commands without starting processes.",
    )
    parser.add_argument(
        "--skip-vllm",
        action="store_true",
        help="Start Redis/LMCache/controller/KV service only.",
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Verify GPU stack dependencies (run scripts/setup_gpu_env.py --check).",
    )
    parser.add_argument(
        "--setup-deps",
        action="store_true",
        help="Install GPU stack dependencies, then verify (scripts/setup_gpu_env.py).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    if args.setup_deps:
        if not SETUP_GPU_ENV.is_file():
            print(
                f"[start.py] error: missing dependency helper {SETUP_GPU_ENV}",
                file=sys.stderr,
            )
            return 1
        cmd = [sys.executable, str(SETUP_GPU_ENV)]
        if args.skip_vllm:
            cmd.append("--skip-vllm")
        result = subprocess.run(cmd, check=False).returncode
        if result != 0:
            return result
    if args.check_deps or args.setup_deps:
        return run_dependency_check(skip_vllm=args.skip_vllm)
    try:
        config = load_config(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[start.py] error: {exc}", file=sys.stderr)
        return 1
    if not args.dry_run:
        dep_code = run_dependency_check(skip_vllm=config.skip_vllm)
        if dep_code != 0:
            print(
                "[start.py] Install deps with: python scripts/setup_gpu_env.py",
                file=sys.stderr,
            )
            return dep_code
    return run_stack(config)


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# cloudflared (run in separate terminals after start.py is up)
#
# Quick tunnels get a random *.trycloudflare.com URL (free, no account needed).
# Only expose KV service + vLLM; keep controller (:9000), MP (:6555/:8080), and
# Redis (:6379) on localhost.
#
# Terminal 1 — KV service gateway (Hostess: LMCACHE_KV_SERVICE_URL)
#   cloudflared tunnel --url http://127.0.0.1:8088
#
# Terminal 2 — vLLM OpenAI API (Hostess: VLLM_BASE_URL and OPENAI_API_BASE_URL)
#   cloudflared tunnel --url http://127.0.0.1:8000
#
# Then set on Hostess (use the https URLs printed by cloudflared):
#   hostess env set LMCACHE_KV_SERVICE_URL=https://<kv-tunnel>.trycloudflare.com
#   hostess env set VLLM_BASE_URL=https://<vllm-tunnel>.trycloudflare.com
#   hostess secret set OPENAI_API_KEY=demo-key
#
# For Open WebUI, OPENAI_API_BASE_URL should be ${VLLM_BASE_URL}/v1 (see hostess.yml).
# ---------------------------------------------------------------------------
