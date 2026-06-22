# SPDX-License-Identifier: Apache-2.0
"""HTTP client for the skills-proxy sidecar."""

# Standard
from typing import Any

# Third Party
import httpx
from fastapi import HTTPException


class SkillsProxy:
    """Forward skills catalog requests to the Node skills-proxy service."""

    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int | bool] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(method, url, params=params)
        if response.status_code >= 400:
            detail: Any = response.text
            try:
                detail = response.json()
            except ValueError:
                pass
            raise HTTPException(status_code=response.status_code, detail=detail)
        if response.status_code == 204:
            return None
        return response.json()

    async def list_skills(
        self,
        *,
        view: str = "all-time",
        page: int = 0,
        per_page: int = 100,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/skills",
            params={"view": view, "page": page, "per_page": per_page},
        )

    async def search_skills(self, *, q: str, limit: int = 50) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/v1/skills/search",
            params={"q": q, "limit": limit},
        )

    async def curated_skills(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/skills/curated")

    async def skill_detail(self, skill_path: str) -> dict[str, Any]:
        normalized = skill_path.strip("/")
        return await self._request("GET", f"/v1/skills/{normalized}")

    async def skill_audit(self, skill_path: str) -> dict[str, Any]:
        normalized = skill_path.strip("/")
        return await self._request("GET", f"/v1/skills/audit/{normalized}")

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/health")
            return True
        except HTTPException:
            return False