# SPDX-License-Identifier: Apache-2.0
"""HTTP proxy to an external LMCache KV service."""

# Standard
from typing import Any

# Third Party
import httpx
from fastapi import HTTPException


class KVServiceProxy:
    """Forward API calls to a running LMCache KV service."""

    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str | int | bool] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(method, url, json=json_body, params=params)
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json()
            except ValueError:
                pass
            raise HTTPException(status_code=response.status_code, detail=detail)
        if response.status_code == 204:
            return None
        return response.json()

    async def register_prompt(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/prompts", json_body=body)

    async def lookup_prompt(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/prompts/lookup", json_body=body)

    async def pin_prompt(self, prompt_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/prompts/{prompt_id}/pin", json_body=body
        )

    async def unpin_prompt(
        self, prompt_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/prompts/{prompt_id}/unpin", json_body=body
        )

    async def evict_prompt(
        self, prompt_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/prompts/{prompt_id}/evict", json_body=body
        )

    async def plan_move(self, prompt_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/prompts/{prompt_id}/move:plan", json_body=body
        )

    async def move_prompt(self, prompt_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", f"/api/prompts/{prompt_id}/move", json_body=body
        )

    async def move_chunk(
        self,
        chunk_hash: str,
        *,
        target: str,
        tenant_id: str,
        source_location: str,
        source_instance_id: str,
        target_instance_id: str,
        copy: bool = False,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/chunks/{chunk_hash}/move",
            params={
                "target": target,
                "tenant_id": tenant_id,
                "source_location": source_location,
                "source_instance_id": source_instance_id,
                "target_instance_id": target_instance_id,
                "copy": copy,
            },
        )

    async def cache_summary(self) -> dict[str, Any]:
        return await self._request("GET", "/api/cache/summary")

    async def list_chunks(
        self,
        tenant_id: str = "",
        location: str = "",
        limit: int = 100,
        offset: int = 0,
        include_debug: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, str | int | bool] = {
            "limit": limit,
            "offset": offset,
            "include_debug": include_debug,
        }
        if tenant_id:
            params["tenant_id"] = tenant_id
        if location:
            params["location"] = location
        return await self._request("GET", "/api/cache/chunks", params=params)

    async def backend_capabilities(self) -> dict[str, Any]:
        return await self._request("GET", "/api/cache/capabilities")

    async def ingest_events(self, since: str = "") -> dict[str, Any]:
        params: dict[str, str] = {}
        if since:
            params["since"] = since
        return await self._request("POST", "/api/cache/events:ingest", params=params)

    async def health_check(self) -> bool:
        try:
            await self.cache_summary()
            return True
        except HTTPException:
            return False
