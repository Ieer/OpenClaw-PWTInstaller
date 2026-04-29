#!/bin/bash

set -e

echo "=== OpenClaw 初始化脚本 ==="

# 创建必要的目录并确保权限正确
mkdir -p /home/node/.openclaw/workspace

# OpenClaw 2026.4.26 may install bundled plugin runtime dependencies after the
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

# If a global/community Feishu extension was installed previously, remove it so we use
# the stock Feishu plugin bundled with OpenClaw (avoids duplicate plugin id warnings).
if [ -d /home/node/.openclaw/extensions/feishu ]; then
  rm -rf /home/node/.openclaw/extensions/feishu || true
fi

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

  python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path('/home/node/.openclaw/openclaw.json')
data = json.loads(path.read_text(encoding='utf-8'))

feishu_app_id = os.environ.get('FEISHU_APP_ID', '').strip()
feishu_app_secret = os.environ.get('FEISHU_APP_SECRET', '').strip()
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

# Remove legacy schema keys that are rejected in newer OpenClaw versions.
if isinstance(feishu_existing, dict):
  feishu_existing.pop('accounts', None)

if feishu_app_id and feishu_app_secret:
  channels['feishu'] = {
    'enabled': True,
    'connectionMode': feishu_existing.get('connectionMode', 'websocket'),
    'dmPolicy': feishu_existing.get('dmPolicy', 'pairing'),
    'groupPolicy': feishu_existing.get('groupPolicy', 'allowlist'),
    'requireMention': feishu_existing.get('requireMention', True),
    'appId': feishu_app_id,
    'appSecret': feishu_app_secret,
  }

  plugins = data.setdefault('plugins', {})
  entries = plugins.setdefault('entries', {})
  entries.setdefault('feishu', {}).update({'enabled': True})

  # Ensure we use stock:feishu (do not keep an installs entry pointing to a global plugin)
  installs = plugins.setdefault('installs', {})
  installs.pop('feishu', None)
elif isinstance(feishu_existing, dict):
  # Keep existing feishu config but with legacy keys removed.
  channels['feishu'] = feishu_existing

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
        echo "✅ 已合并飞书渠道配置（stock:feishu）"
    else
      echo "ℹ️ 未检测到 FEISHU_APP_ID/FEISHU_APP_SECRET，已仅同步 gateway/controlUi 配置"
    fi
fi

# 确保所有文件和目录的权限正确
chown -R node:node /home/node/.openclaw

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
