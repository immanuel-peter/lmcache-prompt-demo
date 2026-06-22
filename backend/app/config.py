# SPDX-License-Identifier: Apache-2.0
"""Runtime configuration for the prompt registry demo API."""

# Standard
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Environment-backed settings for the demo API."""

    lmcache_kv_service_url: str
    lmcache_controller_url: str
    lmcache_runtime_url: str
    vllm_base_url: str
    lmcache_instance_id: str
    demo_tenant_id: str
    sqlite_path: str
    cors_origins: str
    skills_proxy_url: str
    openwebui_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            lmcache_kv_service_url=os.getenv("LMCACHE_KV_SERVICE_URL", "").rstrip("/"),
            lmcache_controller_url=os.getenv(
                "LMCACHE_CONTROLLER_URL", "http://localhost:9000"
            ).rstrip("/"),
            lmcache_runtime_url=os.getenv(
                "LMCACHE_RUNTIME_URL", "http://localhost:8080"
            ).rstrip("/"),
            vllm_base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000").rstrip(
                "/"
            ),
            lmcache_instance_id=os.getenv(
                "LMCACHE_INSTANCE_ID", "lmcache_default_instance"
            ),
            demo_tenant_id=os.getenv("DEMO_TENANT_ID", "demo-tenant"),
            sqlite_path=os.getenv("SQLITE_PATH", ".demo_catalog.sqlite3"),
            cors_origins=os.getenv("CORS_ORIGINS", "*"),
            skills_proxy_url=os.getenv("SKILLS_PROXY_URL", "").rstrip("/"),
            openwebui_url=os.getenv("OPENWEBUI_URL", "http://localhost:8080").rstrip(
                "/"
            ),
        )

    @property
    def use_skills_proxy(self) -> bool:
        """Return whether skills.sh requests should go through the sidecar."""
        return bool(self.skills_proxy_url)

    @property
    def use_proxy(self) -> bool:
        """Return whether requests should be forwarded to an external KV service."""
        return bool(self.lmcache_kv_service_url)

    @property
    def cors_origin_list(self) -> list[str]:
        """Return parsed CORS origins."""
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
