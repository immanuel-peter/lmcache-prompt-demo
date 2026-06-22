# SPDX-License-Identifier: Apache-2.0
"""SQLite-backed skill install registry and staging helpers."""

# Standard
from dataclasses import dataclass
from datetime import UTC, datetime
import sqlite3
from typing import Any

# Third Party
from fastapi import HTTPException

# First Party
from app.models import (
    CacheLocation,
    PromptPinRequest,
    PromptRegistrationRequest,
    SkillInstallRequest,
    SkillInstallResponse,
    SkillUninstallRequest,
    SkillUninstallResponse,
    InstalledSkill,
    InstalledSkillsResponse,
)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(frozen=True, slots=True)
class SkillStagePayload:
    """Prepared prompt body for a skills.sh install."""

    skill_id: str
    name: str
    source: str
    content_hash: str | None
    prompt_text: str


def build_skill_prompt(detail: dict[str, Any]) -> SkillStagePayload:
    """Turn a skills.sh detail payload into staged prompt text."""
    skill_id = str(detail.get("id") or detail.get("source", ""))
    source = str(detail.get("source") or "")
    slug = str(detail.get("slug") or skill_id.split("/")[-1])
    content_hash = detail.get("hash")
    if content_hash is not None:
        content_hash = str(content_hash)

    files = detail.get("files") or []
    parts: list[str] = []
    skill_md = next(
        (f for f in files if str(f.get("path", "")).lower() == "skill.md"),
        None,
    )
    if skill_md and skill_md.get("contents"):
        parts.append(str(skill_md["contents"]))
    else:
        for entry in files:
            path = str(entry.get("path", ""))
            contents = entry.get("contents")
            if not path or not contents:
                continue
            parts.append(f"<!-- {path} -->\n{contents}")

    if not parts:
        parts.append(f"# Skill: {slug}\n\n(Staged from skills.sh catalog entry {skill_id})")

    return SkillStagePayload(
        skill_id=skill_id,
        name=slug,
        source=source,
        content_hash=content_hash,
        prompt_text="\n\n".join(parts),
    )


class SkillInstallStore:
    """Persist skill-to-prompt mappings in SQLite."""

    def __init__(self, sqlite_path: str) -> None:
        self._sqlite_path = sqlite_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_installs (
                    skill_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    prompt_id TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    skill_source TEXT NOT NULL,
                    content_hash TEXT,
                    pin_location TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 1,
                    installed_at TEXT NOT NULL,
                    PRIMARY KEY (skill_id, tenant_id)
                )
                """
            )
            conn.commit()
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(skill_installs)").fetchall()
            }
            if "pinned" not in columns:
                conn.execute(
                    "ALTER TABLE skill_installs ADD COLUMN pinned INTEGER NOT NULL DEFAULT 1"
                )
                conn.commit()

    def list_installed(self, tenant_id: str) -> list[InstalledSkill]:
        with sqlite3.connect(self._sqlite_path) as conn:
            rows = conn.execute(
                """
                SELECT skill_id, skill_name, skill_source, prompt_id,
                       pin_location, installed_at, content_hash, pinned
                FROM skill_installs
                WHERE tenant_id = ?
                ORDER BY installed_at DESC
                """,
                (tenant_id,),
            ).fetchall()
        return [
            InstalledSkill(
                skill_id=row[0],
                name=row[1],
                source=row[2],
                prompt_id=row[3],
                location=row[4],
                pinned=bool(row[7]),
                installed_at=row[5],
                content_hash=row[6],
            )
            for row in rows
        ]

    def upsert(
        self,
        *,
        skill_id: str,
        tenant_id: str,
        prompt_id: str,
        skill_name: str,
        skill_source: str,
        content_hash: str | None,
        pin_location: str,
        pinned: bool,
    ) -> None:
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                """
                INSERT INTO skill_installs
                (skill_id, tenant_id, prompt_id, skill_name, skill_source,
                 content_hash, pin_location, pinned, installed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(skill_id, tenant_id) DO UPDATE SET
                    prompt_id = excluded.prompt_id,
                    skill_name = excluded.skill_name,
                    skill_source = excluded.skill_source,
                    content_hash = excluded.content_hash,
                    pin_location = excluded.pin_location,
                    pinned = excluded.pinned,
                    installed_at = excluded.installed_at
                """,
                (
                    skill_id,
                    tenant_id,
                    prompt_id,
                    skill_name,
                    skill_source,
                    content_hash,
                    pin_location,
                    int(pinned),
                    _now_iso(),
                ),
            )
            conn.commit()

    def remove(self, *, skill_id: str, tenant_id: str) -> str | None:
        with sqlite3.connect(self._sqlite_path) as conn:
            row = conn.execute(
                """
                SELECT prompt_id FROM skill_installs
                WHERE skill_id = ? AND tenant_id = ?
                """,
                (skill_id, tenant_id),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "DELETE FROM skill_installs WHERE skill_id = ? AND tenant_id = ?",
                (skill_id, tenant_id),
            )
            conn.commit()
            return str(row[0])


async def _try_pin_prompt(
    *,
    prompt_id: str,
    tenant_id: str,
    request: SkillInstallRequest,
    instance_id: str,
    catalog: Any | None,
    kv_proxy: Any | None,
) -> tuple[str, bool, str]:
    """Best-effort pin; return (pin_id, pinned, warning)."""
    pin_body = PromptPinRequest(
        tenant_id=tenant_id,
        location=request.location,
        owner="skills-ui",
        ttl_seconds=request.ttl_seconds,
        instance_id=instance_id,
        reason="skills-install",
    )
    try:
        if kv_proxy is not None:
            pin_data = await kv_proxy.pin_prompt(prompt_id, pin_body.model_dump())
            return str(pin_data["pin_id"]), True, ""
        if catalog is not None:
            pin = catalog.pin_prompt(prompt_id, pin_body)
            return pin.pin_id, True, ""
    except HTTPException as exc:
        if exc.status_code >= 500:
            return (
                "",
                False,
                "Skill staged in the catalog, but pin failed on the remote KV service. "
                "Wire LMCACHE_CONTROLLER_URL on the GPU host to enable pinning.",
            )
        raise
    except ValueError as exc:
        return "", False, f"Skill staged in the catalog, but pin was skipped: {exc}"
    raise RuntimeError("No catalog or KV proxy configured.")


async def install_skill(
    *,
    request: SkillInstallRequest,
    tenant_id: str,
    instance_id: str,
    default_model: str,
    skills_proxy: Any,
    catalog: Any | None,
    kv_proxy: Any | None,
    store: SkillInstallStore,
) -> SkillInstallResponse:
    """Fetch, register, pin, and record a skill install."""
    detail = await skills_proxy.skill_detail(request.skill_id)
    staged = build_skill_prompt(detail)

    registration = PromptRegistrationRequest(
        model=default_model,
        prompt=staged.prompt_text,
        tokenizer_id=default_model,
        tenant_id=tenant_id,
        labels={
            "layer": "skills",
            "skill_id": staged.skill_id,
            **({"content_hash": staged.content_hash} if staged.content_hash else {}),
        },
        store_text=True,
    )

    if kv_proxy is not None:
        reg_data = await kv_proxy.register_prompt(registration.model_dump())
        prompt_id = str(reg_data["prompt_id"])
    elif catalog is not None:
        reg = catalog.register_prompt(registration)
        prompt_id = reg.prompt_id
    else:
        raise RuntimeError("No catalog or KV proxy configured.")

    pin_id, pinned, warning = await _try_pin_prompt(
        prompt_id=prompt_id,
        tenant_id=tenant_id,
        request=request,
        instance_id=instance_id,
        catalog=catalog,
        kv_proxy=kv_proxy,
    )

    store.upsert(
        skill_id=staged.skill_id,
        tenant_id=tenant_id,
        prompt_id=prompt_id,
        skill_name=staged.name,
        skill_source=staged.source,
        content_hash=staged.content_hash,
        pin_location=request.location.value,
        pinned=pinned,
    )

    return SkillInstallResponse(
        skill_id=staged.skill_id,
        prompt_id=prompt_id,
        pin_id=pin_id,
        location=request.location.value,
        pinned=pinned,
        warning=warning,
    )


async def uninstall_skill(
    *,
    request: SkillUninstallRequest,
    tenant_id: str,
    catalog: Any | None,
    kv_proxy: Any | None,
    store: SkillInstallStore,
) -> SkillUninstallResponse:
    """Evict staged skill chunks and drop the install record."""
    prompt_id = store.remove(skill_id=request.skill_id, tenant_id=tenant_id)
    if prompt_id is None:
        raise KeyError(f"Skill {request.skill_id} is not installed.")

    warning = ""
    evicted = True
    try:
        if kv_proxy is not None:
            await kv_proxy.evict_prompt(
                prompt_id,
                {
                    "tenant_id": tenant_id,
                    "locations": [
                        CacheLocation.LOCAL_CPU.value,
                        CacheLocation.LOCAL_DISK.value,
                    ],
                    "force": True,
                },
            )
        elif catalog is not None:
            from app.models import PromptEvictRequest

            catalog.evict_prompt(
                prompt_id,
                PromptEvictRequest(
                    tenant_id=tenant_id,
                    locations=[
                        CacheLocation.LOCAL_CPU,
                        CacheLocation.LOCAL_DISK,
                    ],
                    force=True,
                ),
            )
    except HTTPException as exc:
        evicted = False
        if exc.status_code >= 500:
            warning = (
                "Removed the local install record, but remote eviction failed. "
                "The catalog entry may still exist on the KV service."
            )
        else:
            warning = f"Removed the local install record, but eviction failed: {exc.detail}"

    return SkillUninstallResponse(
        skill_id=request.skill_id,
        prompt_id=prompt_id,
        evicted=evicted,
        warning=warning,
    )