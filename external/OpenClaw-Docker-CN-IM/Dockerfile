# OpenClaw Docker 镜像
FROM node:22-slim

# When set to 1, fail the build if plugin installation fails.
ARG STRICT_PLUGIN_INSTALL=0
ARG OPENCLAW_VERSION=2026.5.12
ARG FEISHU_PLUGIN_NPM_SPEC=@m1heng-clawd/feishu@0.1.18
ARG NPM_REGISTRY=https://registry.npmmirror.com

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    chromium \
    curl \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    git \
    gosu \
    jq \
    python3 \
    python3-pip \
    python3-venv \
    python3-yaml \
    socat \
    tini \
    websockify \
  && rm -rf /var/lib/apt/lists/*

# 更新 npm 到稳定版本（避免 npm@latest 在部分环境出现依赖解析异常）
RUN npm install -g npm@10

# 默认使用国内 npm 镜像并放宽网络重试，避免树莓派弱网下 registry 连接重置导致构建失败。
RUN npm config set registry "${NPM_REGISTRY}" \
  && npm config set fetch-retries 8 \
  && npm config set fetch-retry-mintimeout 20000 \
  && npm config set fetch-retry-maxtimeout 120000 \
  && npm config set fetch-timeout 600000

# Ensure npm transitive git dependencies can be fetched without SSH keys
RUN git config --global url."https://github.com/".insteadOf "ssh://git@github.com/" \
  && git config --global url."https://github.com/".insteadOf "git@github.com:"

# 安装 OpenClaw 和 OpenCode AI
RUN npm install -g "openclaw@${OPENCLAW_VERSION}" opencode-ai@latest

# Stock Feishu extension needs its own runtime dependencies alongside the bundled files.
# OpenClaw 2026.5.x may omit the stock Feishu bundle, so keep this optional.
RUN if [ -f /usr/local/lib/node_modules/openclaw/dist/extensions/feishu/package.json ]; then \
    npm install --prefix /usr/local/lib/node_modules/openclaw/dist/extensions/feishu --omit=dev; \
  else \
    echo "[warn] stock feishu extension package.json not found; skip runtime dependency install"; \
  fi

# 安装 Playwright 和 Chromium
RUN npm install -g playwright && npx playwright install chromium --with-deps

# 安装 playwright-extra 和 puppeteer-extra-plugin-stealth
RUN npm install -g playwright-extra puppeteer-extra-plugin-stealth

# 安装 bird
RUN npm install -g @steipete/bird

# 创建配置目录并设置权限（确保 node 用户的 npm cache 不会被 root 污染）
ENV HOME=/home/node \
  TERM=xterm-256color \
  NPM_CONFIG_CACHE=/home/node/.npm \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_NO_CACHE_DIR=1 \
  PYTHONUNBUFFERED=1 \
  OPENCLAW_NPM_REGISTRY=${NPM_REGISTRY} \
  OPENCLAW_FEISHU_PLUGIN_NPM_SPEC=${FEISHU_PLUGIN_NPM_SPEC}

RUN mkdir -p \
    /home/node/.npm \
    /home/node/.openclaw/workspace \
    /home/node/.openclaw/extensions \
    /home/node/.openclaw/qqbot \
  && printf 'registry=%s\nfetch-retries=8\nfetch-retry-mintimeout=20000\nfetch-retry-maxtimeout=120000\nfetch-timeout=600000\n' "${NPM_REGISTRY}" > /home/node/.npmrc \
  && chown -R node:node /home/node

# 切换到 node 用户安装插件
USER node

# Reduce flaky GitHub HTTP2 clone errors
RUN git config --global http.version HTTP/1.1

# 飞书优先使用 OpenClaw 自带 stock:feishu；2026.5.x 缺少 stock bundle 时预装社区 fallback。
RUN set -e; \
  if [ -d /usr/local/lib/node_modules/openclaw/dist/extensions/feishu ] \
    || [ -d /usr/local/lib/node_modules/openclaw/extensions/feishu ]; then \
    echo "[ok] stock feishu extension detected"; \
  else \
    echo "[info] stock feishu extension not found; install community fallback ${FEISHU_PLUGIN_NPM_SPEC}"; \
    (timeout 600 openclaw plugins install "${FEISHU_PLUGIN_NPM_SPEC}") \
    || { if [ "$STRICT_PLUGIN_INSTALL" = "1" ]; then exit 1; else echo "[warn] feishu fallback plugin install skipped"; fi; }; \
  fi

# 安装钉钉插件（从 GitHub clone 后本地安装；失败应让构建失败）
RUN set -e; \
  (rm -rf /tmp/clawdbot-channel-dingtalk \
    && git clone --depth 1 https://github.com/soimy/clawdbot-channel-dingtalk.git /tmp/clawdbot-channel-dingtalk \
    && timeout 600 openclaw plugins install /tmp/clawdbot-channel-dingtalk) \
  || { if [ "$STRICT_PLUGIN_INSTALL" = "1" ]; then exit 1; else echo "[warn] dingtalk plugin install skipped"; fi; }

# 安装 QQ 机器人插件（先 clone 到 /home/node/.openclaw/qqbot，再从本地目录安装）
RUN set -e; \
  (rm -rf /home/node/.openclaw/qqbot/* \
    && git clone --depth 1 https://github.com/justlovemaki/qqbot.git /home/node/.openclaw/qqbot \
    && timeout 600 openclaw plugins install /home/node/.openclaw/qqbot) \
  || { if [ "$STRICT_PLUGIN_INSTALL" = "1" ]; then exit 1; else echo "[warn] qqbot plugin install skipped"; fi; }

# 安装企业微信插件（从 GitHub clone 后本地安装）
RUN set -e; \
  (rm -rf /tmp/openclaw-plugin-wecom \
    && git clone --depth 1 https://github.com/sunnoy/openclaw-plugin-wecom.git /tmp/openclaw-plugin-wecom \
    && timeout 600 openclaw plugins install /tmp/openclaw-plugin-wecom) \
  || { if [ "$STRICT_PLUGIN_INSTALL" = "1" ]; then exit 1; else echo "[warn] wecom plugin install skipped"; fi; }

# 构建期校验（严格模式才强制要求存在）
RUN if [ "$STRICT_PLUGIN_INSTALL" = "1" ]; then test -d /home/node/.openclaw/extensions/dingtalk; fi
RUN if [ "$STRICT_PLUGIN_INSTALL" = "1" ]; then test -d /home/node/.openclaw/extensions/qqbot; fi
RUN if [ "$STRICT_PLUGIN_INSTALL" = "1" ]; then test -d /home/node/.openclaw/extensions/wecom; fi

# 切换回 root 用户继续后续操作
USER root

# OpenClaw 2026.5.x requires external plugin TypeScript entries to have compiled JS output.
RUN npm install -g esbuild@0.24.2

RUN for plugin_dir in \
    /home/node/.openclaw/npm/node_modules/@m1heng-clawd/feishu \
    /home/node/.openclaw/extensions/qqbot; do \
    if [ -f "$plugin_dir/index.ts" ]; then \
      cd "$plugin_dir" \
        && esbuild index.ts --bundle --platform=node --format=esm --target=node22 --packages=external --outfile=index.js \
        && chown node:node index.js; \
    fi; \
  done

# 缓存社区 Feishu fallback；运行时 agent home 由 bind mount 覆盖，init.sh 会按需恢复此缓存。
RUN mkdir -p /opt/openclaw-plugin-cache \
  && if [ -d /home/node/.openclaw/npm/node_modules/@m1heng-clawd/feishu ]; then \
    mkdir -p /opt/openclaw-plugin-cache/npm; \
    cp -a /home/node/.openclaw/npm/. /opt/openclaw-plugin-cache/npm/; \
  fi \
  && if [ -f /home/node/.openclaw/plugins/installs.json ]; then \
    mkdir -p /opt/openclaw-plugin-cache/plugins; \
    cp -a /home/node/.openclaw/plugins/. /opt/openclaw-plugin-cache/plugins/; \
  fi \
  && if [ -d /home/node/.openclaw/extensions/qqbot ]; then \
    mkdir -p /opt/openclaw-plugin-cache/extensions; \
    cp -a /home/node/.openclaw/extensions/qqbot /opt/openclaw-plugin-cache/extensions/qqbot; \
  fi \
  && if [ -d /home/node/.openclaw/qqbot ]; then \
    cp -a /home/node/.openclaw/qqbot /opt/openclaw-plugin-cache/qqbot; \
  fi \
  && chown -R node:node /opt/openclaw-plugin-cache

# 确保 extensions 目录权限正确（排除 node_modules 以加快构建速度）
RUN find /home/node/.openclaw/extensions -type d -name node_modules -prune -o -exec chown node:node {} +

# 复制初始化脚本
COPY ./init.sh /usr/local/bin/init.sh
RUN chmod +x /usr/local/bin/init.sh

# 设置基础环境变量
ENV HOME=/home/node \
  TERM=xterm-256color \
  NPM_CONFIG_CACHE=/home/node/.npm \
  OPENCLAW_FEISHU_PLUGIN_NPM_SPEC=${FEISHU_PLUGIN_NPM_SPEC} \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_NO_CACHE_DIR=1 \
  PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 27216 27217

# 设置工作目录为 home
WORKDIR /home/node

# 使用初始化脚本作为入口点（以 root 运行以便修复权限）
ENTRYPOINT ["/bin/bash", "/usr/local/bin/init.sh"]
