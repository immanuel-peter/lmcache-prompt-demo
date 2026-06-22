# LMCache Prompt Registry Demo

Visual demo for the LMCache prompt registry: decoded KV chunks across **GPU** (observed-only), **CPU**, and **external storage**, with drag-and-drop pin, move, and evict between controllable tiers.

## Stack

| Service     | Tech                                | Purpose                             |
| ----------- | ----------------------------------- | ----------------------------------- |
| `frontend`  | Next.js 16, Tailwind v4, TypeScript | Techno blue/black residency UI      |
| `api`       | FastAPI, Python 3.12                | Prompt registry CRUD + demo catalog |
| `openwebui` | Open WebUI                          | Chat against remote vLLM            |

## Local development

### Backend

```bash
cd backend
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:3000. API defaults to http://localhost:8000.

## GPU stack (Redis + LMCache MP + vLLM)

`scripts/start.py` launches the full live LMCache stack for Hostess/cloudflared demos.
Bootstrap the Python environment **once** (or after LMCache/vLLM upgrades):

```bash
export LMCACHE_REPO=~/LMCache   # path to your LMCache checkout
python scripts/setup_gpu_env.py
```

System packages (not installed by the script):

```bash
sudo apt-get install -y redis-server ninja-build   # ninja is also installed via pip
```

Then start the stack:

```bash
export LMCACHE_PYTHON=~/LMCache/.venv/bin/python
python scripts/start.py
```

Useful flags:

```bash
python scripts/start.py --check-deps    # verify torch/vllm/cupy/redis without starting
python scripts/start.py --setup-deps    # run setup_gpu_env.py, then verify
python scripts/start.py --skip-vllm     # LMCache + KV service only (no GPU model server)
python scripts/start.py --dry-run       # print planned commands
```

`setup_gpu_env.py` installs CUDA-matched wheels explicitly (PyTorch **cu128**, vLLM **cu129**
GitHub wheel, LMCache with `LMCACHE_CUDA_MAJOR=12` for **cupy-cuda12x**, plus **ninja**).
This avoids the common pitfall of `pip install vllm` pulling CUDA 13 binaries.

## Environment variables

### API (`backend`)

| Variable                 | Description                                          | Default                    |
| ------------------------ | ---------------------------------------------------- | -------------------------- |
| `LMCACHE_KV_SERVICE_URL` | Proxy to live LMCache KV service (empty = demo mode) | `""`                       |
| `LMCACHE_CONTROLLER_URL` | LMCache controller API                               | `http://localhost:9000`    |
| `LMCACHE_RUNTIME_URL`    | LMCache MP HTTP server                               | `http://localhost:8080`    |
| `VLLM_BASE_URL`          | vLLM OpenAI-compatible API                           | `http://localhost:8000`    |
| `LMCACHE_INSTANCE_ID`    | Runtime instance ID                                  | `lmcache_default_instance` |
| `DEMO_TENANT_ID`         | Default tenant for UI                                | `demo-tenant`              |
| `SQLITE_PATH`            | Demo catalog SQLite path                             | `.demo_catalog.sqlite3`    |
| `CORS_ORIGINS`           | Allowed CORS origins                                 | `*`                        |

### Frontend

| Variable                    | Description                  |
| --------------------------- | ---------------------------- |
| `NEXT_PUBLIC_API_URL`       | Demo API base URL            |
| `NEXT_PUBLIC_OPENWEBUI_URL` | Open WebUI URL for chat link |

### Hostess / Open WebUI

Set these on deploy (Hostess dashboard or `hostess env set`):

- `VLLM_BASE_URL` — e.g. `https://your-vllm.example.com`
- `VLLM_DEFAULT_MODEL` — e.g. `meta-llama/Llama-3.1-8B-Instruct`
- `LMCACHE_KV_SERVICE_URL` — optional; point at production KV service for proxy mode
- `LMCACHE_CONTROLLER_URL` / `LMCACHE_RUNTIME_URL` — when using live LMCache
- Secret `OPENAI_API_KEY` — any non-empty string (vLLM often ignores it)

## UI interactions

- **Register Prompt** — POST `/api/prompts`, tokenizes and catalogs chunks
- **Drag CPU ↔ External** — move chunks between tiers
- **Double-click chunk** — pin at current tier (TTL 1h)
- **Drop on evict zone** — evict from current tier
- **GPU column** — read-only; toast explains pinning is not wired yet

## Deploy on Hostess

```bash
hostess validate
hostess deploy --env production
```

Set `VLLM_BASE_URL` and `OPENAI_API_KEY` secret before first deploy.

## Connect to real LMCache

1. Run LMCache KV service (from the LMCache repo) with controller/runtime URLs configured.
2. Set `LMCACHE_KV_SERVICE_URL` on the demo API to the KV service URL.
3. Redeploy — UI switches to **proxy mode** and uses live catalog data.
