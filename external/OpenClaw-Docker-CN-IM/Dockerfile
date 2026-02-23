# OpenClaw Docker 镜像
FROM node:22-slim

# When set to 1, fail the build if plugin installation fails.
ARG STRICT_PLUGIN_INSTALL=0

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
    socat \
    tini \
    websockify \
  && rm -rf /var/lib/apt/lists/*

# 更新 npm 到最新版本
RUN npm install -g npm@latest

# 安装 OpenClaw 和 OpenCode AI
RUN npm install -g openclaw@latest opencode-ai@latest

# 安装 Playwright 和 Chromium
RUN npm install -g playwright && npx playwright install chromium --with-deps

# 安装 playwright-extra 和 puppeteer-extra-plugin-stealth
RUN npm install -g playwright-extra puppeteer-extra-plugin-stealth

# 安装 bird
RUN npm install -g @steipete/bird

# 创建配置目录并设置权限（确保 node 用户的 npm cache 不会被 root 污染）
ENV HOME=/home/node \
  TERM=xterm-256color \
  NPM_CONFIG_CACHE=/home/node/.npm

RUN mkdir -p \
    /home/node/.npm \
    /home/node/.openclaw/workspace \
    /home/node/.openclaw/extensions \
    /home/node/.openclaw/qqbot \
  && chown -R node:node /home/node

# 切换到 node 用户安装插件
USER node

# Reduce flaky GitHub HTTP2 clone errors
RUN git config --global http.version HTTP/1.1

# 飞书使用 OpenClaw 自带 stock:feishu（不再额外安装社区插件，避免 duplicate plugin id）
RUN test -d /usr/local/lib/node_modules/openclaw/extensions/feishu

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

# 确保 extensions 目录权限正确（排除 node_modules 以加快构建速度）
RUN find /home/node/.openclaw/extensions -type d -name node_modules -prune -o -exec chown node:node {} +

# 复制初始化脚本
COPY ./init.sh /usr/local/bin/init.sh
RUN chmod +x /usr/local/bin/init.sh

# 设置基础环境变量
ENV HOME=/home/node \
  TERM=xterm-256color \
  NPM_CONFIG_CACHE=/home/node/.npm

# 暴露端口
EXPOSE 27216 27217

# 设置工作目录为 home
WORKDIR /home/node

# 使用初始化脚本作为入口点（以 root 运行以便修复权限）
ENTRYPOINT ["/bin/bash", "/usr/local/bin/init.sh"]
