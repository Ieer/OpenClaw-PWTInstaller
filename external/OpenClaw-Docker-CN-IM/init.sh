#!/bin/bash

set -e

echo "=== OpenClaw 初始化脚本 ==="

# 创建必要的目录并确保权限正确
mkdir -p /home/node/.openclaw/workspace

# Recent OpenClaw releases may install bundled plugin runtime dependencies after the
# gateway has started. The image-level npm config is created during build as
# root, so make the runtime node user's npm config explicit as well; otherwise
# those startup installs fall back to registry.npmjs.org and can hang long enough
# to make /chat/<agent>/ look like a blank page.
OPENCLAW_NPM_REGISTRY="${OPENCLAW_NPM_REGISTRY:-${NPM_REGISTRY:-https://registry.npmmirror.com}}"
cat > /home/node/.npmrc <<EOF
registry=${OPENCLAW_NPM_REGISTRY}
fetch-retries=8
fetch-retry-mintimeout=20000
fetch-retry-maxtimeout=120000
fetch-timeout=600000
EOF
chown node:node /home/node/.npmrc

OPENCLAW_FEISHU_PLUGIN_NPM_SPEC="${OPENCLAW_FEISHU_PLUGIN_NPM_SPEC:-@m1heng-clawd/feishu@0.1.18}"
OPENCLAW_FEISHU_PLUGIN_VERSION="${OPENCLAW_FEISHU_PLUGIN_NPM_SPEC##*@}"

stock_feishu_available() {
  local candidate
  for candidate in \
    /usr/local/lib/node_modules/openclaw/dist/extensions/feishu \
    /usr/local/lib/node_modules/openclaw/extensions/feishu; do
    if [ -f "$candidate/index.js" ] || [ -f "$candidate/index.ts" ] || [ -f "$candidate/openclaw.plugin.json" ]; then
      return 0
    fi
  done
  return 1
}

community_feishu_version() {
  local package_json=/home/node/.openclaw/npm/node_modules/@m1heng-clawd/feishu/package.json
  if [ ! -f "$package_json" ]; then
    return 1
  fi
  node -e 'const fs=require("fs"); const p=process.argv[1]; process.stdout.write(JSON.parse(fs.readFileSync(p,"utf8")).version || "")' "$package_json"
}

community_feishu_available() {
  local version
  version="$(community_feishu_version 2>/dev/null || true)"
  [ "$version" = "$OPENCLAW_FEISHU_PLUGIN_VERSION" ]
}

community_feishu_registered() {
  local registry_json=/home/node/.openclaw/plugins/installs.json
  if [ ! -f "$registry_json" ]; then
    return 1
  fi
  node -e '
const fs = require("fs");
const registryPath = process.argv[1];
const expectedVersion = process.argv[2];
const expectedPath = "/home/node/.openclaw/npm/node_modules/@m1heng-clawd/feishu";
try {
  const registry = JSON.parse(fs.readFileSync(registryPath, "utf8"));
  const record = registry && registry.installRecords && registry.installRecords.feishu;
  if (!record || !record.installPath) process.exit(1);
  if (record.installPath !== expectedPath) process.exit(1);
  const packageJsonPath = `${record.installPath}/package.json`;
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));
  if (packageJson.version !== expectedVersion) process.exit(1);
  const plugins = Array.isArray(registry.plugins) ? registry.plugins : [];
  if (!plugins.some((plugin) => plugin && plugin.pluginId === "feishu")) process.exit(1);
} catch {
  process.exit(1);
}
' "$registry_json" "$OPENCLAW_FEISHU_PLUGIN_VERSION"
}

register_community_feishu_plugin() {
  mkdir -p /home/node/.openclaw/extensions /home/node/.openclaw/npm /home/node/.npm
  chown node:node /home/node/.openclaw /home/node/.openclaw/openclaw.json 2>/dev/null || true
  chown node:node /home/node/.openclaw/extensions /home/node/.openclaw/npm /home/node/.npm 2>/dev/null || true

  echo "[info] registering community feishu fallback from image registry cache"
  rm -rf /home/node/.openclaw/extensions/feishu 2>/dev/null || true
  restore_cached_feishu_registry && community_feishu_registered
}

restore_cached_feishu_plugin() {
  local cache_dir=/opt/openclaw-plugin-cache/npm
  if [ ! -f "$cache_dir/node_modules/@m1heng-clawd/feishu/package.json" ]; then
    return 1
  fi
  mkdir -p /home/node/.openclaw/npm
  cp -a "$cache_dir/." /home/node/.openclaw/npm/
  chown -R node:node /home/node/.openclaw/npm 2>/dev/null || true
}

restore_cached_feishu_registry() {
  local cache_dir=/opt/openclaw-plugin-cache/plugins
  if [ ! -f "$cache_dir/installs.json" ]; then
    return 1
  fi
  mkdir -p /home/node/.openclaw/plugins
  cp -a "$cache_dir/." /home/node/.openclaw/plugins/
  chown -R node:node /home/node/.openclaw/plugins 2>/dev/null || true
}

ensure_feishu_plugin_available() {
  if stock_feishu_available; then
    # Stock plugin is preferred when OpenClaw bundles it; remove community copies to avoid duplicate plugin ids.
    rm -rf /home/node/.openclaw/extensions/feishu \
      /home/node/.openclaw/npm/node_modules/@m1heng-clawd/feishu 2>/dev/null || true
    echo "[ok] stock:feishu available"
    return 0
  fi

  if community_feishu_available; then
    if community_feishu_registered; then
      echo "[ok] community feishu fallback registered (${OPENCLAW_FEISHU_PLUGIN_VERSION})"
      return 0
    fi
    if register_community_feishu_plugin && community_feishu_registered; then
      echo "[ok] registered community feishu fallback (${OPENCLAW_FEISHU_PLUGIN_VERSION})"
      return 0
    fi
    echo "[warn] community feishu fallback package exists but registration failed; Feishu channel may be unavailable"
    return 0
  fi

  rm -rf /home/node/.openclaw/extensions/feishu \
    /home/node/.openclaw/npm/node_modules/@m1heng-clawd/feishu 2>/dev/null || true

  if restore_cached_feishu_plugin && community_feishu_available; then
    if community_feishu_registered; then
      echo "[ok] restored registered community feishu fallback from image cache (${OPENCLAW_FEISHU_PLUGIN_VERSION})"
      return 0
    fi
    if register_community_feishu_plugin && community_feishu_registered; then
      echo "[ok] restored and registered community feishu fallback from image cache (${OPENCLAW_FEISHU_PLUGIN_VERSION})"
      return 0
    fi
    echo "[warn] restored community feishu fallback but registration failed; Feishu channel may be unavailable"
    return 0
  fi

  if register_community_feishu_plugin && community_feishu_registered; then
    echo "[ok] installed community feishu fallback (${OPENCLAW_FEISHU_PLUGIN_VERSION})"
    return 0
  fi

  echo "[warn] failed to install community feishu fallback; Feishu channel may be unavailable"
  return 0
}

# Stock runtime bundles under plugin-runtime-deps import the bare "openclaw" package.
# Bridge that import back to the global install so stock plugins can resolve it.
ensure_openclaw_runtime_bridge() {
  local global_openclaw=/usr/local/lib/node_modules/openclaw
  local runtime_node_modules=/home/node/.openclaw/plugin-runtime-deps/node_modules
  local runtime_openclaw="$runtime_node_modules/openclaw"

  if [ ! -d "$global_openclaw" ]; then
    echo "[warn] global openclaw package not found; skip runtime bridge"
    return
  fi

  mkdir -p "$runtime_node_modules"

  if [ -L "$runtime_openclaw" ]; then
    local current_target
    current_target="$(readlink -f "$runtime_openclaw" || true)"
    if [ "$current_target" = "$global_openclaw" ]; then
      return
    fi
    rm -f "$runtime_openclaw"
  elif [ -e "$runtime_openclaw" ]; then
    return
  fi

  ln -s "$global_openclaw" "$runtime_openclaw"
  echo "[ok] bridged plugin-runtime-deps/openclaw to global package"
}

fix_openclaw_permissions() {
  local root=/home/node/.openclaw

  # Full recursive chown on Panopticon bind mounts is very expensive once
  # sessions/, workspaces/, reports, or media artifacts grow. Keep startup fast
  # by fixing only root/config files and writable directory ownership. Operators
  # can still opt in to the old deep repair with OPENCLAW_FIX_PERMISSIONS_DEEP=1.
  if [ "${OPENCLAW_FIX_PERMISSIONS_DEEP:-0}" = "1" ]; then
    echo "ℹ️ 执行深度权限修复: $root"
    chown -R node:node "$root"
    return
  fi

  chown node:node /home/node "$root" 2>/dev/null || true

  find "$root" -maxdepth 1 -type f -exec chown node:node {} + 2>/dev/null || true
  find "$root" -maxdepth 3 -type d -exec chown node:node {} + 2>/dev/null || true

  for dir in \
    "$root/agents" \
    "$root/canvas" \
    "$root/data" \
    "$root/extensions" \
    "$root/logs" \
    "$root/plugin-runtime-deps" \
    "$root/workspace"; do
    if [ -d "$dir" ]; then
      find "$dir" -maxdepth 2 -type d -exec chown node:node {} + 2>/dev/null || true
      find "$dir" -maxdepth 1 -type f -exec chown node:node {} + 2>/dev/null || true
    fi
  done
}

# 检查配置文件是否存在，如果不存在则生成
if [ ! -f /home/node/.openclaw/openclaw.json ]; then
    echo "生成配置文件..."
    
    # 从环境变量读取配置参数
    MODEL_ID="${MODEL_ID}"
    BASE_URL="${BASE_URL}"
    API_KEY="${API_KEY}"
    API_PROTOCOL="${API_PROTOCOL:-openai-completions}"
    OPENCLAW_VERSION="${OPENCLAW_VERSION:-unknown}"
    CONTEXT_WINDOW="${CONTEXT_WINDOW:-200000}"
    MAX_TOKENS="${MAX_TOKENS:-8192}"
    
    TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
    FEISHU_APP_ID="${FEISHU_APP_ID}"
    FEISHU_APP_SECRET="${FEISHU_APP_SECRET}"
    DINGTALK_CLIENT_ID="${DINGTALK_CLIENT_ID}"
    DINGTALK_CLIENT_SECRET="${DINGTALK_CLIENT_SECRET}"
    DINGTALK_ROBOT_CODE="${DINGTALK_ROBOT_CODE:-$DINGTALK_CLIENT_ID}"
    DINGTALK_CORP_ID="${DINGTALK_CORP_ID}"
    DINGTALK_AGENT_ID="${DINGTALK_AGENT_ID}"
    QQBOT_APP_ID="${QQBOT_APP_ID}"
    QQBOT_CLIENT_SECRET="${QQBOT_CLIENT_SECRET}"
    WECOM_TOKEN="${WECOM_TOKEN}"
    WECOM_ENCODING_AES_KEY="${WECOM_ENCODING_AES_KEY}"
    WORKSPACE="${WORKSPACE}"
    OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT}"
    OPENCLAW_GATEWAY_BIND="${OPENCLAW_GATEWAY_BIND}"
    OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN}"
    OPENCLAW_GATEWAY_AUTH_MODE="${OPENCLAW_GATEWAY_AUTH_MODE:-token}"
    OPENCLAW_GATEWAY_PASSWORD="${OPENCLAW_GATEWAY_PASSWORD}"
    OPENCLAW_CONTROL_UI_DISABLE_DEVICE_AUTH="${OPENCLAW_CONTROL_UI_DISABLE_DEVICE_AUTH:-1}"
    OPENCLAW_COMPACTION_RESERVE_TOKENS_FLOOR="${OPENCLAW_COMPACTION_RESERVE_TOKENS_FLOOR:-32000}"
    
    # 生成配置文件
    cat > /home/node/.openclaw/openclaw.json <<EOF
{
  "meta": {
    "lastTouchedVersion": "$OPENCLAW_VERSION",
    "lastTouchedAt": "$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")"
  },
  "update": {
    "checkOnStart": false
  },
  "browser": {
    "headless": true,
    "noSandbox": true,
    "defaultProfile": "openclaw",
    "executablePath": "/usr/bin/chromium"
  },
  "models": {
    "mode": "merge",
    "providers": {
      "default": {
        "baseUrl": "$BASE_URL",
        "apiKey": "$API_KEY",
        "api": "$API_PROTOCOL",
        "models": [
          {
            "id": "$MODEL_ID",
            "name": "$MODEL_ID",
            "reasoning": false,
            "input": ["text", "image"],
            "cost": {
              "input": 0,
              "output": 0,
              "cacheRead": 0,
              "cacheWrite": 0
            },
            "contextWindow": $CONTEXT_WINDOW,
            "maxTokens": $MAX_TOKENS
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "default/$MODEL_ID"
      },
      "imageModel": {
        "primary": "default/$MODEL_ID"
      },
      "workspace": "$WORKSPACE",
      "compaction": {
        "mode": "safeguard",
        "reserveTokensFloor": $OPENCLAW_COMPACTION_RESERVE_TOKENS_FLOOR
      },
      "elevatedDefault": "full",
      "maxConcurrent": 4,
      "subagents": {
        "maxConcurrent": 8
      }
    }
  },
  "messages": {
    "ackReactionScope": "group-mentions"
  },
  "commands": {
    "native": "auto",
    "nativeSkills": "auto"
  },
  "channels": {
EOF

    # 添加 Telegram 配置（如果提供了 token）
    FIRST_CHANNEL=true
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        cat >> /home/node/.openclaw/openclaw.json <<EOF
    "telegram": {
      "dmPolicy": "pairing",
      "botToken": "$TELEGRAM_BOT_TOKEN",
      "groupPolicy": "allowlist",
      "streamMode": "partial"
    }
EOF
        FIRST_CHANNEL=false
    fi

    # 添加飞书配置（如果提供了 APP_ID 和 APP_SECRET）
    if [ -n "$FEISHU_APP_ID" ] && [ -n "$FEISHU_APP_SECRET" ]; then
        if [ "$FIRST_CHANNEL" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
    "feishu": {
      "enabled": true,
      "connectionMode": "websocket",
      "dmPolicy": "pairing",
      "groupPolicy": "allowlist",
      "requireMention": true,
      "appId": "$FEISHU_APP_ID",
      "appSecret": "$FEISHU_APP_SECRET"
    }
EOF
        FIRST_CHANNEL=false
    fi

    # 添加钉钉配置（如果提供了 CLIENT_ID 和 CLIENT_SECRET）
    if [ -n "$DINGTALK_CLIENT_ID" ] && [ -n "$DINGTALK_CLIENT_SECRET" ]; then
        if [ "$FIRST_CHANNEL" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
    "dingtalk": {
      "enabled": true,
      "clientId": "$DINGTALK_CLIENT_ID",
      "clientSecret": "$DINGTALK_CLIENT_SECRET",
      "robotCode": "$DINGTALK_ROBOT_CODE",
      "corpId": "$DINGTALK_CORP_ID",
      "agentId": "$DINGTALK_AGENT_ID",
      "dmPolicy": "open",
      "groupPolicy": "open",
      "messageType": "markdown",
      "debug": false
    }
EOF
        FIRST_CHANNEL=false
    fi

    # 添加 QQ 机器人配置（如果提供了 APP_ID 和 CLIENT_SECRET）
    if [ -n "$QQBOT_APP_ID" ] && [ -n "$QQBOT_CLIENT_SECRET" ]; then
        if [ "$FIRST_CHANNEL" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
    "qqbot": {
      "enabled": true,
      "appId": "$QQBOT_APP_ID",
      "clientSecret": "$QQBOT_CLIENT_SECRET"
    }
EOF
        FIRST_CHANNEL=false
    fi

    # 添加企业微信配置（如果提供了必需参数）
    if [ -n "$WECOM_TOKEN" ] && [ -n "$WECOM_ENCODING_AES_KEY" ]; then
        if [ "$FIRST_CHANNEL" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
    "wecom": {
      "enabled": true,
      "token": "$WECOM_TOKEN",
      "encodingAesKey": "$WECOM_ENCODING_AES_KEY"
    }
EOF
    fi

    # 关闭 channels 对象
    cat >> /home/node/.openclaw/openclaw.json <<EOF
  },
  "gateway": {
    "port": $OPENCLAW_GATEWAY_PORT,
    "mode": "local",
    "bind": "$OPENCLAW_GATEWAY_BIND",
    "controlUi": {
      "allowInsecureAuth": true,
      "dangerouslyDisableDeviceAuth": $OPENCLAW_CONTROL_UI_DISABLE_DEVICE_AUTH
    },
    "auth": {
      "mode": "$OPENCLAW_GATEWAY_AUTH_MODE",
      "token": "$OPENCLAW_GATEWAY_TOKEN",
      "password": "$OPENCLAW_GATEWAY_PASSWORD"
    }
  },
  "plugins": {
    "entries": {
EOF

    # 添加 Telegram 插件配置（如果提供了 token）
    FIRST_PLUGIN=true
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        cat >> /home/node/.openclaw/openclaw.json <<EOF
      "telegram": {
        "enabled": true
      }
EOF
        FIRST_PLUGIN=false
    fi

    # 添加飞书插件配置（如果提供了 APP_ID 和 APP_SECRET）
    if [ -n "$FEISHU_APP_ID" ] && [ -n "$FEISHU_APP_SECRET" ]; then
        if [ "$FIRST_PLUGIN" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
      "feishu": {
        "enabled": true
      }
EOF
        FIRST_PLUGIN=false
    fi

    # 添加钉钉插件配置（如果提供了 CLIENT_ID 和 CLIENT_SECRET）
    if [ -n "$DINGTALK_CLIENT_ID" ] && [ -n "$DINGTALK_CLIENT_SECRET" ]; then
        if [ "$FIRST_PLUGIN" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
      "dingtalk": {
        "enabled": true
      }
EOF
        FIRST_PLUGIN=false
    fi

    # 添加 QQ 机器人插件配置（如果提供了 APP_ID 和 CLIENT_SECRET）
    if [ -n "$QQBOT_APP_ID" ] && [ -n "$QQBOT_CLIENT_SECRET" ]; then
        if [ "$FIRST_PLUGIN" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
      "qqbot": {
        "enabled": true
      }
EOF
        FIRST_PLUGIN=false
    fi

    # 添加企业微信插件配置（如果提供了必需参数）
    if [ -n "$WECOM_TOKEN" ] && [ -n "$WECOM_ENCODING_AES_KEY" ]; then
        if [ "$FIRST_PLUGIN" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
      "openclaw-plugin-wecom": {
        "enabled": true
      }
EOF
    fi

    # 关闭 entries 对象
    cat >> /home/node/.openclaw/openclaw.json <<EOF
    },
    "installs": {
EOF

    # NOTE: Feishu is available as a stock plugin in OpenClaw.
    # We intentionally do NOT add plugins.installs.feishu here to avoid pulling a second
    # global/community plugin that may cause duplicate plugin id warnings.
    FIRST_INSTALL=true

    # 添加钉钉插件安装信息（如果提供了 CLIENT_ID 和 CLIENT_SECRET）
    if [ -n "$DINGTALK_CLIENT_ID" ] && [ -n "$DINGTALK_CLIENT_SECRET" ]; then
        if [ "$FIRST_INSTALL" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
      "dingtalk": {
        "source": "npm",
        "spec": "https://github.com/soimy/clawdbot-channel-dingtalk.git",
        "installPath": "/home/node/.openclaw/extensions/dingtalk",
        "installedAt": "$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")"
      }
EOF
        FIRST_INSTALL=false
    fi

    # 添加 QQ 机器人插件安装信息（如果提供了 APP_ID 和 CLIENT_SECRET）
    if [ -n "$QQBOT_APP_ID" ] && [ -n "$QQBOT_CLIENT_SECRET" ]; then
        if [ "$FIRST_INSTALL" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
      "qqbot": {
        "source": "path",
        "sourcePath": "/home/node/.openclaw/qqbot",
        "installPath": "/home/node/.openclaw/extensions/qqbot",
        "installedAt": "$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")"
      }
EOF
        FIRST_INSTALL=false
    fi

    # 添加企业微信插件安装信息（如果提供了必需参数）
    if [ -n "$WECOM_TOKEN" ] && [ -n "$WECOM_ENCODING_AES_KEY" ]; then
        if [ "$FIRST_INSTALL" = false ]; then
            echo "," >> /home/node/.openclaw/openclaw.json
        fi
        cat >> /home/node/.openclaw/openclaw.json <<EOF
      "openclaw-plugin-wecom": {
        "source": "npm",
        "spec": "https://github.com/sunnoy/openclaw-plugin-wecom.git",
        "installPath": "/home/node/.openclaw/extensions/openclaw-plugin-wecom",
        "installedAt": "$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")"
      }
EOF
    fi

    # 关闭 installs 和 plugins 对象
    cat >> /home/node/.openclaw/openclaw.json <<EOF
    }
  }
}
EOF

    echo "✅ 配置文件已生成"
else
    echo "配置文件已存在，尝试按环境变量合并渠道/插件配置"

    FEISHU_APP_ID="${FEISHU_APP_ID}"
    FEISHU_APP_SECRET="${FEISHU_APP_SECRET}"
  OPENCLAW_GATEWAY_BIND="${OPENCLAW_GATEWAY_BIND}"
  OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT}"
  OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN}"
  OPENCLAW_GATEWAY_AUTH_MODE="${OPENCLAW_GATEWAY_AUTH_MODE:-token}"
  OPENCLAW_GATEWAY_PASSWORD="${OPENCLAW_GATEWAY_PASSWORD}"
  OPENCLAW_CONTROL_UI_DISABLE_DEVICE_AUTH="${OPENCLAW_CONTROL_UI_DISABLE_DEVICE_AUTH:-1}"
  OPENCLAW_COMPACTION_RESERVE_TOKENS_FLOOR="${OPENCLAW_COMPACTION_RESERVE_TOKENS_FLOOR:-32000}"
  if stock_feishu_available; then
    OPENCLAW_STOCK_FEISHU_AVAILABLE=1
  else
    OPENCLAW_STOCK_FEISHU_AVAILABLE=0
  fi
  export OPENCLAW_STOCK_FEISHU_AVAILABLE

  python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path('/home/node/.openclaw/openclaw.json')
data = json.loads(path.read_text(encoding='utf-8'))

feishu_app_id = os.environ.get('FEISHU_APP_ID', '').strip()
feishu_app_secret = os.environ.get('FEISHU_APP_SECRET', '').strip()
stock_feishu_available = os.environ.get('OPENCLAW_STOCK_FEISHU_AVAILABLE', '').strip() == '1'
gateway_bind = os.environ.get('OPENCLAW_GATEWAY_BIND', '').strip() or 'lan'
gateway_port_raw = os.environ.get('OPENCLAW_GATEWAY_PORT', '').strip() or '26216'
gateway_token = os.environ.get('OPENCLAW_GATEWAY_TOKEN', '').strip()
gateway_auth_mode = os.environ.get('OPENCLAW_GATEWAY_AUTH_MODE', '').strip() or 'token'
gateway_password = os.environ.get('OPENCLAW_GATEWAY_PASSWORD', '').strip()
reserve_tokens_floor_raw = os.environ.get('OPENCLAW_COMPACTION_RESERVE_TOKENS_FLOOR', '').strip() or '32000'
disable_device_auth_raw = os.environ.get('OPENCLAW_CONTROL_UI_DISABLE_DEVICE_AUTH', '').strip().lower()
disable_device_auth = disable_device_auth_raw not in {'', '0', 'false', 'no', 'off'}

try:
  gateway_port = int(gateway_port_raw)
except ValueError:
  gateway_port = 26216

try:
  reserve_tokens_floor = int(reserve_tokens_floor_raw)
except ValueError:
  reserve_tokens_floor = 32000

gateway = data.setdefault('gateway', {})
gateway['port'] = gateway_port
gateway['mode'] = gateway.get('mode', 'local')
gateway['bind'] = gateway_bind
control_ui = gateway.setdefault('controlUi', {})
control_ui['allowInsecureAuth'] = True
control_ui['dangerouslyDisableDeviceAuth'] = disable_device_auth

auth = gateway.setdefault('auth', {})
auth['mode'] = gateway_auth_mode
if gateway_token:
  auth['token'] = gateway_token
else:
  auth.pop('token', None)
if gateway_password:
  auth['password'] = gateway_password
else:
  auth.pop('password', None)

agents = data.setdefault('agents', {})
defaults = agents.setdefault('defaults', {})
compaction = defaults.setdefault('compaction', {})
compaction['mode'] = compaction.get('mode', 'safeguard') or 'safeguard'
compaction['reserveTokensFloor'] = reserve_tokens_floor

# Current OpenClaw schema no longer accepts messages.tts.edge.
messages = data.get('messages') if isinstance(data.get('messages'), dict) else None
if messages is not None:
  tts = messages.get('tts') if isinstance(messages.get('tts'), dict) else None
  if tts is not None:
    tts.pop('edge', None)
    if not tts:
      messages.pop('tts', None)

channels = data.setdefault('channels', {})
feishu_existing = channels.get('feishu') if isinstance(channels.get('feishu'), dict) else {}

def normalize_allow_list(value):
  if isinstance(value, list):
    return [str(item).strip() for item in value if str(item).strip()]
  if value is None:
    return []
  item = str(value).strip()
  return [item] if item else []

def ensure_feishu_open_policy_allowlist(config):
  if config.get('dmPolicy') == 'open':
    allow_from = normalize_allow_list(config.get('allowFrom'))
    if not any(entry == '*' for entry in allow_from):
      allow_from.append('*')
    config['allowFrom'] = allow_from
  return config

# Remove legacy schema keys that are rejected in newer OpenClaw versions.
if isinstance(feishu_existing, dict):
  feishu_existing.pop('accounts', None)

if feishu_app_id and feishu_app_secret:
  feishu_config = {
    'enabled': True,
    'connectionMode': feishu_existing.get('connectionMode', 'websocket'),
    'dmPolicy': feishu_existing.get('dmPolicy', 'pairing'),
    'groupPolicy': feishu_existing.get('groupPolicy', 'allowlist'),
    'requireMention': feishu_existing.get('requireMention', True),
    'appId': feishu_app_id,
    'appSecret': feishu_app_secret,
  }
  for key in (
    'allowFrom',
    'groupAllowFrom',
    'domain',
    'webhookPath',
    'reactionNotifications',
    'typingIndicator',
    'resolveSenderNames',
    'encryptKey',
    'verificationToken',
  ):
    if key in feishu_existing:
      feishu_config[key] = feishu_existing[key]
  channels['feishu'] = ensure_feishu_open_policy_allowlist(feishu_config)

  plugins = data.setdefault('plugins', {})
  entries = plugins.setdefault('entries', {})
  entries.setdefault('feishu', {}).update({'enabled': True})

  # Prefer stock:feishu when bundled; when it is absent, init.sh provides a community fallback package.
  installs = plugins.setdefault('installs', {})
  if stock_feishu_available:
    installs.pop('feishu', None)
elif isinstance(feishu_existing, dict):
  # Keep existing feishu config but with legacy keys removed.
  channels['feishu'] = ensure_feishu_open_policy_allowlist(feishu_existing)

feishu_configured = channels.get('feishu') if isinstance(channels.get('feishu'), dict) else None
if feishu_configured and feishu_configured.get('enabled', True):
  plugins = data.setdefault('plugins', {})
  entries = plugins.setdefault('entries', {})
  entries.setdefault('feishu', {}).update({'enabled': True})
  allow = plugins.get('allow')
  if not isinstance(allow, list):
    allow = []
  if 'feishu' not in allow:
    allow.append('feishu')
  plugins['allow'] = allow

# Cleanup stale plugin path configs so OpenClaw can start even if old linked plugins were removed.
plugins = data.setdefault('plugins', {})
load = plugins.get('load') if isinstance(plugins.get('load'), dict) else None
if load is not None:
  paths = load.get('paths')
  if isinstance(paths, list):
    valid_paths: list[str] = []
    removed_paths: list[str] = []
    for plugin_path in paths:
      plugin_path_str = str(plugin_path).strip()
      if not plugin_path_str:
        continue
      if Path(plugin_path_str).exists():
        valid_paths.append(plugin_path_str)
      else:
        removed_paths.append(plugin_path_str)
    if removed_paths:
      print(f"ℹ️ 已移除失效插件路径: {', '.join(removed_paths)}")
    if valid_paths:
      load['paths'] = valid_paths
      plugins['load'] = load
    else:
      plugins.pop('load', None)

path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
    if [ -n "$FEISHU_APP_ID" ] && [ -n "$FEISHU_APP_SECRET" ]; then
        if stock_feishu_available; then
          echo "✅ 已合并飞书渠道配置（stock:feishu）"
        else
          echo "✅ 已合并飞书渠道配置（community feishu fallback）"
        fi
    else
      echo "ℹ️ 未检测到 FEISHU_APP_ID/FEISHU_APP_SECRET，已仅同步 gateway/controlUi 配置"
    fi
fi

python3 - <<'PY'
import json
from pathlib import Path

path = Path('/home/node/.openclaw/openclaw.json')
if path.exists():
  data = json.loads(path.read_text(encoding='utf-8'))
  channels = data.get('channels') if isinstance(data.get('channels'), dict) else {}
  feishu = channels.get('feishu') if isinstance(channels.get('feishu'), dict) else None
  if feishu and feishu.get('enabled', True):
    plugins = data.setdefault('plugins', {})
    entries = plugins.setdefault('entries', {})
    entries.setdefault('feishu', {}).update({'enabled': True})
    allow = plugins.get('allow')
    if not isinstance(allow, list):
      allow = []
    if 'feishu' not in allow:
      allow.append('feishu')
    plugins['allow'] = allow
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY

ensure_feishu_plugin_available

# 确保关键文件和目录权限正确；默认避免深度遍历大型会话/工作区目录。
fix_openclaw_permissions

ensure_openclaw_runtime_bridge

echo "=== 初始化完成 ==="
echo "当前使用模型: default/$MODEL_ID"
echo "API 协议: ${API_PROTOCOL:-openai-completions}"
echo "Base URL: ${BASE_URL}"
echo "上下文窗口: ${CONTEXT_WINDOW:-200000}"
echo "最大 Tokens: ${MAX_TOKENS:-8192}"
echo "Gateway 端口: $OPENCLAW_GATEWAY_PORT"
echo "Gateway 绑定: $OPENCLAW_GATEWAY_BIND"

# 启动 OpenClaw Gateway（切换到 node 用户）
echo "=== 启动 OpenClaw Gateway ==="

# 定义清理函数
cleanup() {
    echo "=== 接收到停止信号,正在关闭服务 ==="
    if [ -n "$GATEWAY_PID" ]; then
        kill -TERM "$GATEWAY_PID" 2>/dev/null || true
        wait "$GATEWAY_PID" 2>/dev/null || true
    fi
    echo "=== 服务已停止 ==="
    exit 0
}

# 捕获终止信号
trap cleanup SIGTERM SIGINT SIGQUIT

is_port_open() {
  local host="$1"
  local port="$2"

  (echo >"/dev/tcp/$host/$port") >/dev/null 2>&1
}

print_startup_diagnostics() {
  echo "=== OpenClaw Gateway 启动诊断 ==="
  echo "Gateway PID: ${GATEWAY_PID:-unknown}"
  echo "Gateway 端口: ${OPENCLAW_GATEWAY_PORT:-unset}"
  echo "Bridge 端口: ${OPENCLAW_BRIDGE_PORT:-unset}"
  openclaw --version 2>/dev/null || true
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp || true
  elif command -v netstat >/dev/null 2>&1; then
    netstat -ltnp || true
  else
    echo "未找到 ss/netstat，跳过监听端口明细"
  fi
}

wait_for_port() {
  local host="$1"
  local port="$2"
  local label="$3"
  local timeout_seconds="${4:-300}"
  local waited=0

  while [ "$waited" -lt "$timeout_seconds" ]; do
    if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
      echo "❌ $label 等待失败：Gateway 进程已退出"
      return 2
    fi
    if is_port_open "$host" "$port"; then
      echo "✅ $label 已监听 ($host:$port, ${waited}s)"
      return 0
    fi
    sleep 2
    waited=$((waited + 2))
  done

  echo "❌ $label 等待超时 ($host:$port, ${timeout_seconds}s)"
  return 1
}

# 在后台启动 OpenClaw Gateway 作为子进程。
# 当前 OpenClaw 将前台容器运行入口收敛到 `gateway run`；裸 `gateway`
# 只处理服务管理命令，容器内会启动一个不监听端口的 systemd 管理流程。
gosu node env HOME=/home/node openclaw gateway run --verbose &
GATEWAY_PID=$!

echo "=== OpenClaw Gateway 已启动 (PID: $GATEWAY_PID) ==="

GATEWAY_READY_TIMEOUT="${OPENCLAW_GATEWAY_READY_TIMEOUT:-300}"
BRIDGE_READY_TIMEOUT="${OPENCLAW_BRIDGE_READY_TIMEOUT:-300}"
BRIDGE_READY_REQUIRED="${OPENCLAW_BRIDGE_READY_REQUIRED:-1}"

if ! wait_for_port "127.0.0.1" "${OPENCLAW_GATEWAY_PORT:-26216}" "OpenClaw Gateway" "$GATEWAY_READY_TIMEOUT"; then
  print_startup_diagnostics
  kill -TERM "$GATEWAY_PID" 2>/dev/null || true
  wait "$GATEWAY_PID" 2>/dev/null || true
  exit 1
fi

if [ -n "${OPENCLAW_BRIDGE_PORT:-}" ] && [ "$BRIDGE_READY_REQUIRED" != "0" ]; then
  if ! wait_for_port "127.0.0.1" "$OPENCLAW_BRIDGE_PORT" "OpenClaw Bridge" "$BRIDGE_READY_TIMEOUT"; then
    print_startup_diagnostics
    kill -TERM "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
    exit 1
  fi
fi

# 主进程等待子进程
wait "$GATEWAY_PID"
EXIT_CODE=$?

echo "=== OpenClaw Gateway 已退出 (退出码: $EXIT_CODE) ==="
exit $EXIT_CODE
