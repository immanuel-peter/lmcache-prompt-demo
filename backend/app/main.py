# SPDX-License-Identifier: Apache-2.0
"""FastAPI application entrypoint."""

# Third Party
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# First Party
from app.config import Settings
from app.demo_service import DemoCatalog
from app.proxy import KVServiceProxy
from app.routes import router
from app.skills_install import SkillInstallStore
from app.skills_proxy import SkillsProxy


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the demo FastAPI application."""
    resolved = settings or Settings.from_env()
    app = FastAPI(
        title="LMCache Prompt Registry Demo",
        version="0.1.0",
        description="Visual demo API for LMCache prompt registry CRUD and chunk residency.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = resolved
    app.state.proxy = (
        KVServiceProxy(resolved.lmcache_kv_service_url) if resolved.use_proxy else None
    )
    app.state.skills_proxy = (
        SkillsProxy(resolved.skills_proxy_url) if resolved.use_skills_proxy else None
    )
    app.state.skill_installs = SkillInstallStore(resolved.sqlite_path)
    app.state.catalog = (
        None
        if resolved.use_proxy
        else DemoCatalog(
            sqlite_path=resolved.sqlite_path,
            instance_id=resolved.lmcache_instance_id,
            tenant_id=resolved.demo_tenant_id,
        )
    )

    app.include_router(router)
    return app


app = create_app()
