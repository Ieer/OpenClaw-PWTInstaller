from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "agents.manifest.yaml"
COMPOSE_PATH = ROOT / "docker-compose.panopticon.yml"
ENV_DIR = ROOT / "env"
TEMPLATE_PATH = ROOT / "templates" / "agent.env.tpl"


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("manifest must be a mapping")
    return data


def render_compose(manifest: dict) -> str:
    mission_control = manifest["mission_control"]
    runtime = manifest["agent_runtime"]
    agents = [agent for agent in manifest["agents"] if agent.get("enabled", True)]
    agent_slugs = ",".join(agent["slug"] for agent in agents)

    compose_header = textwrap.dedent(
        """\
        # AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY.
        # Source of truth: panopticon/agents.manifest.yaml
        # Generator: panopticon/tools/generate_panopticon.py

        services:
          mc-redis:
            container_name: mc-redis
            image: redis:7-alpine
            command: [\"redis-server\", \"--appendonly\", \"yes\"]
            volumes:
              - type: bind
                source: ${{PANOPTICON_DATA_DIR:-.}}/mission-control/redis-data
                target: /data
            restart: unless-stopped
            networks:
              - panopticon

          mc-postgres:
            container_name: mc-postgres
            image: pgvector/pgvector:pg16
            environment:
              POSTGRES_USER: mission_control
              POSTGRES_PASSWORD: mission_control
              POSTGRES_DB: mission_control
            volumes:
              - type: bind
                source: ${{PANOPTICON_DATA_DIR:-.}}/mission-control/postgres-data
                target: /var/lib/postgresql/data
              - type: bind
                source: ./mission-control/db
                target: /docker-entrypoint-initdb.d
                read_only: true
            restart: unless-stopped
            networks:
              - panopticon

          mission-control-api:
            container_name: mission-control-api
            build:
              context: ../mission_control_api
              dockerfile: Dockerfile
            image: mission-control-api:local
            env_file:
              - ./env/mission-control.env.example
            depends_on:
              - mc-redis
              - mc-postgres
            ports:
              - \"{api_port}:9090\"
            restart: unless-stopped
            networks:
              - panopticon

          mission-control-ui:
            container_name: mission-control-ui
            build:
              context: ../MissionControl
              dockerfile: Dockerfile
            image: mission-control-ui:local
            env_file:
              - ./env/mission-control-ui.env.example
            volumes:
              - type: bind
                source: ./agents.manifest.yaml
                target: /app/panopticon_agents.manifest.yaml
                read_only: true
            depends_on:
              - mission-control-api
            ports:
              - \"{ui_port}:9090\"
            restart: unless-stopped
            networks:
              - panopticon

          mc-heartbeat:
            container_name: mc-heartbeat
            image: python:3.12-alpine
            env_file:
              - ./env/mission-control.env.example
            environment:
              MC_API_URL: http://mission-control-api:9090
              MC_HEARTBEAT_AGENTS: {agent_slugs}
              MC_HEARTBEAT_INTERVAL_SECONDS: "60"
            volumes:
              - type: bind
                source: ./tools/heartbeat_emitter.py
                target: /app/heartbeat_emitter.py
                read_only: true
            command: ["python", "/app/heartbeat_emitter.py"]
            depends_on:
              - mission-control-api
            restart: unless-stopped
            networks:
              - panopticon
        """
    ).format(api_port=mission_control["api_port"], ui_port=mission_control["ui_port"], agent_slugs=agent_slugs)

    services_text = []
    for agent in agents:
        slug = agent["slug"]
        gateway_host_port = agent["gateway_host_port"]
        bridge_host_port = agent["bridge_host_port"]

        service_block = textwrap.dedent(
            """\
            openclaw-{slug}:
              container_name: openclaw-{slug}
              build:
                context: {cnim_build_context}
                dockerfile: {cnim_dockerfile}
              image: {cnim_image}
              cap_add:
                - CHOWN
                - SETUID
                - SETGID
                - DAC_OVERRIDE
              environment:
                HOME: /home/node
                TERM: xterm-256color
              env_file:
                - ./env/{slug}.env.example
              volumes:
                - type: bind
                  source: ${{PANOPTICON_DATA_DIR:-.}}/agent-homes/{slug}
                  target: /home/node/.openclaw
                - type: bind
                  source: ${{PANOPTICON_DATA_DIR:-.}}/workspaces/{slug}
                  target: /home/node/.openclaw/workspace
                - /home/node/.openclaw/extensions
              ports:
                - \"{gateway_host_port}:{gateway_container_port}\"
                - \"{bridge_host_port}:{bridge_container_port}\"
              init: true
              restart: unless-stopped
              networks:
                - panopticon

            """
        ).format(
            slug=slug,
            cnim_build_context=runtime["cnim_build_context"],
            cnim_dockerfile=runtime["cnim_dockerfile"],
            cnim_image=runtime["cnim_image"],
            gateway_host_port=gateway_host_port,
            bridge_host_port=bridge_host_port,
            gateway_container_port=runtime["container_gateway_port"],
            bridge_container_port=runtime["container_bridge_port"],
        )
        services_text.append(textwrap.indent(service_block, "  "))

    footer = textwrap.dedent(
        """

        networks:
          panopticon:
            driver: bridge
        """
    )

    return compose_header + "".join(services_text) + footer


def render_agent_env(template: str, agent: dict) -> str:
    return template.format(
        slug=agent["slug"],
        role=agent.get("role", "agent"),
        gateway_token=agent.get("gateway_token", f"CHANGE_ME_{agent['slug'].upper()}"),
    )


def generate(manifest_path: Path, prune: bool = False) -> None:
    manifest = load_manifest(manifest_path)

    compose_content = render_compose(manifest)
    COMPOSE_PATH.write_text(compose_content, encoding="utf-8")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    ENV_DIR.mkdir(parents=True, exist_ok=True)

    active_slugs: set[str] = set()
    for agent in manifest["agents"]:
        if not agent.get("enabled", True):
            continue
        slug = agent["slug"]
        active_slugs.add(slug)
        env_content = render_agent_env(template, agent)
        (ENV_DIR / f"{slug}.env.example").write_text(env_content, encoding="utf-8")

    if prune:
        static_files = {
            "mission-control.env.example",
            "mission-control-ui.env.example",
        }
        for env_file in ENV_DIR.glob("*.env.example"):
            if env_file.name in static_files:
                continue
            slug = env_file.name.removesuffix(".env.example")
            if slug not in active_slugs:
                env_file.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate panopticon compose/env from agents.manifest.yaml"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help="Path to agents.manifest.yaml",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete stale env/*.env.example not present in enabled agents",
    )
    args = parser.parse_args()

    generate(args.manifest, prune=args.prune)
    print(f"Generated: {COMPOSE_PATH}")
    print(f"Generated env templates in: {ENV_DIR}")
