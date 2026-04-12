# 真实语音设备联调指南

这份文档只讲一件事：怎么把真实语音设备接到当前仓库里的 Mission Control 语音桥接链路。

目标不是“跑通合成 demo”，而是尽快定位真实设备联调会卡在哪一层。

## 先明确当前链路

当前仓库里的语音链路分四段：

1. 真实设备或外部语音栈发布 ROS2 话题。
2. `mission-control-voice-bridge` 订阅这些话题，转成 `voice.*` 事件。
3. Mission Control API 接收事件，写入 feed，并按需触发语音直控。
4. Mission Control UI 展示 overlay、feed 和任务/状态变化。

一句话记忆：**设备发 ROS2，桥接器发事件，Mission Control 做治理。**

## 推荐联调拓扑

真实设备联调优先按下面顺序选：

### 模式 A：设备语音栈和桥接器在同一 ROS2 主机上

这是最稳的方案。

- 设备驱动 / ASR / TTS 节点跑在同一台 ROS2 主机。
- `mission-control-voice-bridge` 跑在 Docker 里，但能看到同一 ROS2 图。
- Mission Control API / UI 继续走 Panopticon Compose。

### 模式 B：设备在局域网另一台 ROS2 主机上

这时最大风险不是 Mission Control，而是 **DDS 发现和 Docker 网络**。

- 如果桥接容器看不到远端 ROS2 话题，先不要怀疑业务代码。
- 优先确认 ROS2 发现、域 ID、防火墙和组播。
- 第一轮联调如果卡在 DDS，建议临时把桥接器直接跑在宿主机 ROS2 环境中，而不是继续困在 Docker 网络里。

### 模式 C：只想先验证业务链路，不关心真实麦克风

先跑仓库自带的 synthetic E2E：

```bash
bash panopticon/tools/test_voice_bridge_e2e.sh
```

这一步过了，再接真实设备，排障边界会清晰很多。

## 联调前置条件

至少满足下面 5 项：

1. Panopticon 主路线已经跑起来。
2. `mission-control-api` 健康可用。
3. 语音桥接 profile 已启用。
4. 真实设备侧知道自己要发布哪些 ROS2 话题。
5. 你已经确认是否需要开启语音直控。

最小检查命令：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml up -d
docker compose -f panopticon/docker-compose.panopticon.yml --profile voice up -d mission-control-voice-bridge
curl -fsS http://127.0.0.1:18910/health
```

## 更好的评估方法

如果你想评估的是“语音服务整体是否完成闭环”，优先跑新的分层评估脚本：

```bash
python panopticon/tools/assess_voice_service.py
```

它会把下面几层分开报告：

- API 健康
- ROS2 话题可见性
- synthetic bridge smoke
- 直接 `voice.asr.final -> voice.command.executed / task.created` 闭环

如果你暂时不想让脚本创建一个临时 DONE 任务，可以加：

```bash
python panopticon/tools/assess_voice_service.py --skip-command-closure
```

## 必要配置

### 1. `panopticon/env/mission-control.env`

先从 example 复制：

```bash
cp panopticon/env/mission-control.env.example panopticon/env/mission-control.env
```

通常至少要确认：

- `MC_AUTH_TOKEN`
如果 API 开了鉴权，桥接器写事件必须带同一个 token。

- `MC_VOICE_COMMANDS_ENABLED=1`
开启语音直控适配器。

- `MC_VOICE_COMMAND_REQUIRE_PREFIX=1`
建议保留开启，避免普通对话被当成控制指令。

- `MC_VOICE_COMMAND_PREFIXES=指挥,mission control,control`
默认值够用。

说明：当前仓库已经在 voice bridge 容器里显式注入 `MC_API_URL=http://mission-control-api:9090`，所以标准 compose 启动时不需要你再手工补这一项。

### 2. `panopticon/env/mission-control-voice-bridge.env`

先复制：

```bash
cp panopticon/env/mission-control-voice-bridge.env.example panopticon/env/mission-control-voice-bridge.env
```

这个文件只管桥接器自己的行为，关键项如下：

- `MC_VOICE_AGENT=voice-engine`
事件里显示的语音 agent 名称。

- `MC_VOICE_TOPIC_WAKEUP=wakeup`
- `MC_VOICE_TOPIC_ASR=asr`
- `MC_VOICE_TOPIC_TEXT_RESPONSE=text_response`
- `MC_VOICE_TOPIC_TTS=tts_topic`

这些值必须和真实设备侧发布的话题名一致。

- `MC_VOICE_ENABLE_LLM_FIRST_TOKEN=1`
如果你的文本响应链路也会发 `text_response`，建议开启。

- `MC_VOICE_IDLE_AFTER_TTS_S=6.0`
控制 speaking 回 idle 的时间窗口。

- `MC_VOICE_BRIDGE_LOG_PAYLOAD=1`
只在排障时临时打开，平时建议保持 `0`。

## 真实设备侧需要对齐什么

桥接器当前订阅的就是 4 类 ROS2 话题：

- `wakeup`，类型 `std_msgs/msg/Bool`
- `asr`，类型 `std_msgs/msg/String`
- `text_response`，类型 `std_msgs/msg/String`
- `tts_topic`，类型 `std_msgs/msg/String`

桥接逻辑如下：

- `wakeup=true`：写 `voice.state = listening`
- `asr` 文本：写 `voice.asr.final`，同时切 `voice.state = thinking`
- `text_response`：写 `voice.llm.first_token`
- `tts_topic`：写 `voice.tts.start`，同时切 `voice.state = speaking`

如果你的设备侧命名不同，有两种方式：

1. 改设备侧发布的话题名。
2. 改 `mission-control-voice-bridge.env` 中的 `MC_VOICE_TOPIC_*`。

## 标准联调顺序

### 第 1 步：先跑 synthetic E2E

如果你的目标是“评估而不是单纯 smoke”，优先改跑上一节的 `assess_voice_service.py`。

```bash
bash panopticon/tools/test_voice_bridge_e2e.sh
```

这一步确认的是：

- 桥接器容器在跑。
- 事件能写回 Mission Control API。
- feed-lite 能看到 `voice.state`、`voice.asr.final`、`voice.tts.start`。

### 第 2 步：启动真实设备语音栈

这一步按你的设备方案来做，但最低要求是能把话题发到和桥接器同一个 ROS2 图里。

### 第 3 步：观察 live 话题和 live 事件

仓库里新增了一个实时联调脚本：

```bash
bash panopticon/tools/check_voice_bridge_live.sh
```

它会做三件事：

1. 检查 `mission-control-voice-bridge` 是否在运行。
2. 列出桥接器容器当前能看到的 ROS2 话题。
3. 轮询 Mission Control `feed-lite`，等待 live `voice.*` 事件出现。

默认等待 60 秒，且默认要求至少看到：

- `voice.state`
- `voice.asr.final`

你可以按需覆盖：

```bash
MC_VOICE_LIVE_TIMEOUT_S=90 \
MC_VOICE_EXPECT_EVENT_TYPES=voice.state,voice.asr.final,voice.tts.start \
bash panopticon/tools/check_voice_bridge_live.sh
```

### 第 4 步：验证语音直控

如果你开启了语音直控，就说一条带前缀的显式命令，例如：

- `指挥 创建任务 给 metrics：统计过去 7 天各 Agent 活跃度；标签：reporting,panopticon`
- `指挥 评论任务 3fa2c1d0：请先给结论，再给依据`

如果命令被执行，会在 feed 里看到：

- `voice.command.executed`
- 相应的 `task.created` / `comment.created` / `task.status` / `task.handoff`

如果命令被拒绝，会看到：

- `voice.command.rejected`

## 看到什么算联调成功

最低成功标准：

1. 说唤醒词后，feed 里出现 `voice.state(listening)`。
2. 说一句普通话后，feed 里出现 `voice.asr.final`。
3. 如果设备侧已经打通播报，feed 里出现 `voice.tts.start`。
4. 如果开启语音直控，说一条带前缀命令后，Mission Control 任务板或 feed 发生对应变化。

## 典型排障顺序

### 现象 1：桥接器容器是 running，但完全看不到 live 话题

优先排查：

- 真实设备侧是否真的在发布 ROS2 话题。
- 设备侧和桥接器是否在同一个 `ROS_DOMAIN_ID`。
- Docker 网络是否阻断 DDS 发现。

如果真实设备在外部主机或局域网，且桥接容器看不到话题，优先把问题归到 **ROS2 发现 / Docker 网络**，不要先怀疑 Mission Control API。

### 现象 2：桥接器能看到 ROS2 话题，但 feed 里没有 `voice.*`

优先排查：

- `MC_AUTH_TOKEN` 是否正确。
- `MC_API_URL` 是否可达。
- 桥接容器日志里是否有发送失败、401、403、5xx。

命令：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml logs --tail=120 mission-control-voice-bridge
```

### 现象 3：能看到 `voice.asr.final`，但语音直控没触发

优先排查：

- `MC_VOICE_COMMANDS_ENABLED` 是否为 `1`。
- `MC_VOICE_COMMAND_REQUIRE_PREFIX` 是否为 `1`，以及你说的话是否带了前缀。
- 说的是不是显式命令语法，而不是自然闲聊。

### 现象 4：只有 synthetic E2E 通过，真实设备一直失败

这通常说明：

- Mission Control 业务链路没问题。
- 问题大概率在设备侧 ROS2 话题、DDS 发现、网络隔离，或者设备根本没发到桥接器能看到的图里。

## 建议的联调策略

第一轮不要一上来就测“完整语音对话”。

建议顺序是：

1. synthetic E2E
2. live ROS2 话题可见性
3. live `voice.asr.final`
4. live `voice.tts.start`
5. 语音直控任务创建
6. 语音直控 handoff / 状态流转

这样每一层失败都能快速定位，不会把问题混成一团。