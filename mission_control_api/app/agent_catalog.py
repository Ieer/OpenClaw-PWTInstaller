from __future__ import annotations

from pathlib import Path

import yaml

from .config import Settings, _is_placeholder_token


def _slug_label(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title() or slug


def _load_manifest_data(path: str | None) -> dict:
    manifest_path = Path(str(path or "").strip())
    if not manifest_path.exists() or not manifest_path.is_file():
        return {}

    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return data if isinstance(data, dict) else {}


def build_agent_catalog(settings: Settings) -> list[dict]:
    manifest = _load_manifest_data(settings.agent_manifest_path)
    agents = manifest.get("agents") if isinstance(manifest.get("agents"), list) else []

    out: list[dict] = []
    seen: set[str] = set()
    for idx, item in enumerate(agents):
        if not isinstance(item, dict):
            continue

        slug = str(item.get("slug") or "").strip()
        if not slug or slug in seen:
            continue

        seen.add(slug)

        gateway_port_raw = item.get("gateway_host_port")
        bridge_port_raw = item.get("bridge_host_port")
        try:
            gateway_host_port = int(gateway_port_raw) if gateway_port_raw is not None else None
        except (TypeError, ValueError):
            gateway_host_port = None
        try:
            bridge_host_port = int(bridge_port_raw) if bridge_port_raw is not None else None
        except (TypeError, ValueError):
            bridge_host_port = None

        token_candidate = settings.agent_token_map.get(slug) or str(item.get("gateway_token") or "").strip()
        gateway_token = "" if _is_placeholder_token(token_candidate) else token_candidate
        direct_url = ""
        if settings.enable_direct_agent_links and gateway_host_port:
            direct_url = f"http://{settings.chat_host}:{gateway_host_port}"

        out.append(
            {
                "slug": slug,
                "label": _slug_label(slug),
                "enabled": bool(item.get("enabled", True)),
                "gateway_host_port": gateway_host_port,
                "bridge_host_port": bridge_host_port,
                "direct_url": direct_url,
                "embed_path": f"/chat/{slug}/",
                "gateway_token": gateway_token,
                "open_mode": "iframe",
                "order": idx,
            }
        )

    if out:
        return out

    fallback_slugs = [part.strip() for part in str(settings.agent_slugs).split(",") if part.strip()]
    return [
        {
            "slug": slug,
            "label": _slug_label(slug),
            "enabled": True,
            "gateway_host_port": None,
            "bridge_host_port": None,
            "direct_url": "",
            "embed_path": f"/chat/{slug}/",
            "gateway_token": settings.agent_token_map.get(slug, ""),
            "open_mode": "iframe",
            "order": idx,
        }
        for idx, slug in enumerate(fallback_slugs)
    ]