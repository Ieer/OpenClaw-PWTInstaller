# ============================================================
# OpenClaw Docker 镜像
# 
# 构建: docker build -t openclaw .
# 运行: docker run -d --name openclaw -v ~/.openclaw:/root/.openclaw openclaw
# ============================================================

FROM node:22-alpine

ARG OPENCLAW_VERSION=2026.5.7
ARG NPM_REGISTRY=https://registry.npmmirror.com

LABEL maintainer="OpenClaw Community"
LABEL description="OpenClaw - Your Personal AI Assistant"
LABEL version="1.0.0"
LABEL org.opencontainers.image.version="${OPENCLAW_VERSION}"

# 安装基础依赖
RUN apk add --no-cache \
    bash \
    curl \
    git \
    jq \
    py3-pip \
    py3-yaml \
    py3-virtualenv \
    python3 \
    tzdata

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 创建工作目录
WORKDIR /app

# 默认使用国内 npm 镜像并放宽网络重试，避免弱网下 registry 连接重置导致构建失败。
RUN npm config set registry "${NPM_REGISTRY}" \
    && npm config set fetch-retries 8 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm config set fetch-timeout 600000

# 安装 OpenClaw
RUN npm install -g "openclaw@${OPENCLAW_VERSION}"

# 创建配置目录
RUN mkdir -p /root/.openclaw/logs \
    /root/.openclaw/data \
    /root/.openclaw/skills \
    /root/.openclaw/backups

# 复制默认配置和技能
COPY examples/config.example.yaml /root/.openclaw/config.yaml.example
COPY examples/skills/ /root/.openclaw/skills/

# 设置卷挂载点
VOLUME ["/root/.openclaw"]

# 暴露端口
EXPOSE 26216

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD openclaw health || exit 1

# 入口脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["openclaw", "start", "--daemon"]
