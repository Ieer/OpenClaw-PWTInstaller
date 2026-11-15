# 真实语音设备联调指南

这份文档只讲一件事：怎么把真实语音设备接到当前仓库里的 Mission Control 语音桥接链路。

目标不是“跑通合成 demo”，而是尽快定位真实设备联调会卡在哪一层。

## 先明确当前链路

当前仓库里的语音链路分四段：

1. 真实设备或外部语音栈发布 ROS2 话题。
2. `mission-control-voice-bridge` 订阅这些话题，转成 `voice.*` 事件。
3. Mission Control API 接收事件，写入 feed，并按需触发语音直控；执行或拒绝后可写入 `voice.tts.requested`，作为设备侧播报反馈请求。
4. Mission Control UI 展示 overlay、feed 和任务/状态变化。

一句话记忆：**设备发 ROS2，桥接器发事件，Mission Control 做治理。**

## 浏览器文字与语音

### 局域网设备自动批准排障

首次连接顺序是 **Gateway token 认证 → 浏览器签名设备配对 → 会话连接**。自动批准脚本只处理第二步；停在 “This Gateway expects its token” 时，不会产生待配对请求，也不能用自动批准代替 token。请在浏览器中直接输入 token，勿发到聊天、日志或仓库中。

八个角色的交互式终端 token 查看命令及对应页面登录步骤，见 [CLI 速查表的 Panopticon 浏览器认证](openclaw-cli-cheatsheet-zh-cn.md#panopticon-浏览器认证2026113-已核验)。

`auto_approve_control_ui_repairs.js` 默认 dry-run，通过原生 `devices list/approve` CLI 工作，不再跨 Agent 继承信任。生效策略须明确角色列表、私有 LAN CIDR、权限、请求年龄、次数上限和截止时间；当前八角色授权仅允许 `192.168.1.3/32`。完整 Control UI 的管理/审批/配对权限要求显式 `allowAdmin=true`，已有设备权限升级仍要求人工确认。

日志状态包括 `monitor-started`、`inventory-checked`、拒绝原因、`scan-complete` 和 `monitor-stopped`。单个角色 CLI 失败会记录 `inventory-unavailable` 并继续其他角色；批准结果不确定时记录 `approval-outcome-unknown`，不自动重试，并保守消耗一次额度。原生 CLI 顺序查询八个角色可能约需 40 秒，10 秒间隔是在整轮查询完成后开始。

同一策略的次数持久保存在 `control-ui-auto-approve.policy.json.state.json`，服务重启不重置额度；独占 `.lock` 防止同时启动两份 apply 监控。策略、状态和锁文件被 Git 忽略且为私有权限；异常强制终止可能留下锁，需确认没有活动进程后才能人工清理，不能直接绕过锁。不要在无人授权时延长策略截止时间或重置次数。

检查配置与当前候选（不批准）：

```bash
node panopticon/tools/auto_approve_control_ui_repairs.js \
	--policy panopticon/env/control-ui-auto-approve.policy.json
```

本次经用户确认的新窗口由独立 systemd 用户服务 `openclaw-control-ui-auto-approve-20261115-085158.service` 管理，截止北京时间 2026-11-15 09:21:23，最多消耗 8 次批准尝试，不是永久后台授权。查看日志和停止：

```bash
journalctl --user --no-pager -u openclaw-control-ui-auto-approve-20261115-085158.service -n 30
systemctl --user stop openclaw-control-ui-auto-approve-20261115-085158.service
```

服务独立于编辑器终端，并有运行时间上限；过期或额度耗尽后不会自动创建新窗口。脚本不填写登录密钥、不关闭 Gateway 认证，也不改变浏览器麦克风权限。

### Personal UI 单角色试点（2026-11-15）

personal 初次通过原生配置 CLI 接入显式音频 CLI 转写、Microsoft TTS（中文 Xiaoxiao）和 `talk.realtime.mode=stt-tts`。原生 Microsoft 客户端出现 403 后，语音输出已改用下述内部兼容接口。文字、听写和 Talk 仍属于同一个原生 WebChat 会话；没有新增会话数据库，也没有更改 personal 原模型、渠道和 Gateway 认证。`tts.auto=off`，普通文字回复不自动播报，用户可手动 Read aloud 或开启 Talk。

`agent-speech` 是八角色可复用的单路 ASR/TTS 适配服务，不是另一套 Agent。浏览器上传的音频由所选角色的原生音频 CLI 转发给它；服务使用 ffmpeg 解码为单声道 PCM WAV，按模型转换为 8 kHz 或 16 kHz，然后调用 DashScope。最大输入 3 MiB、最大时长 30 秒；忙时拒绝新请求，不自动重试。适配服务不发布主机端口，只有容器网络可达。各角色使用独立 token，共享服务不等于共享聊天会话、私有知识或工具权限。

明文 DashScope key 仅在私有 `panopticon/env/agent-speech.json` 中，角色客户端只持有自己的独立服务 token：`agent-homes/<role>/voice/speech-client.json`。这些文件权限 600 且被 Git 忽略。`prepare` 从指定私有 YAML 读取凭据，不打印秘密；更换 provider key 后重新准备并重建服务，重复准备不会自动轮换 token。服务侧私有 key 与 token 应成套备份，权限 600 不等于加密。

```bash
python3 panopticon/tools/agent_speech.py prepare \
	--source /home/pi/yahboom_ws/src/largemodel/config/large_model_interface.yaml \
	--credentials panopticon/env/agent-speech.json \
	--client panopticon/agent-homes/personal/voice/speech-client.json

docker compose -p panopticon \
	-f panopticon/docker-compose.panopticon.yml \
	-f panopticon/docker-compose.lan-https.yml \
	-f panopticon/docker-compose.execution-worker.yml \
	-f panopticon/docker-compose.agent-speech.yml \
	--profile voice-ui up -d --no-deps agent-speech
```

新原生 CLI 配置里的执行路径是 `/home/node/.openclaw/voice/agent_speech.py`，须与受版本控制的 `panopticon/tools/agent_speech.py` 同步；传入 `{{AttachmentPath}}`，不是手工读取 UI DOM。此脚本只访问固定的内部 ASR 服务地址，不使用环境 HTTP 代理或跟随重定向。初次部署仍须用原生 `openclaw config set --batch-json ... --dry-run` 验证 `tools.media.models`、`tts`、`talk` 和 provider 插件白名单；不能覆盖其他角色或已有模型配置。

共享组件现统一为 `agent_speech.py`、`test_agent_speech.py`、`Dockerfile.agent-speech`、`docker-compose.agent-speech.yml` 和 `agent-speech:local`。旧 `personal_speech.py` 只保留兼容 CLI 入口；同步旧入口到角色目录时须同时同步新模块。新 compose 保留 `personal-speech` DNS 别名和 `personal-voice` profile，旧 URL 仍可被客户端识别，但新配置默认使用 `http://agent-speech:18081`。`personal` 的角色标识和历史 token 不改名、不轮换。

2026-11-15 10:24 已完成运行迁移：`agent-speech:local` 容器 `agent-speech` 健康，新旧 DNS 名 `agent-speech` 和 `personal-speech` 均指向它。旧容器保留为停止且断网的 `personal-speech-rollback-20261115-102449`，回滚镜像为 `agent-speech:rollback-20261115-102449`；新旧私有配置完全一致，没有轮换 token。此次只迁移语音服务，八个 Agent 启动时间和重启计数未变；现有 personal CLI 路径继续兼容，没有顺带应用其他角色的语音配置。

以后完整迁移其他角色时，须同步各角色 CLI 路径并逐项 dry-run、应用；现有自定义语音配置不得直接覆盖。代码支持八角色独立 token，不代表八个角色均已配置或完成真实浏览器语音验收。

若本次迁移后发生故障，可仅切回保留的语音容器，不执行整套 compose down：

```bash
docker stop agent-speech
docker network disconnect panopticon_panopticon agent-speech
docker network connect --alias agent-speech --alias personal-speech \
	panopticon_panopticon personal-speech-rollback-20261115-102449
docker start personal-speech-rollback-20261115-102449
```

回滚后不要同时启动新旧容器，避免兼容 DNS 别名同时指向两份服务。回滚容器和旧配置用于本次恢复，不能随意执行 `--remove-orphans` 清理。

进入可信 HTTPS 的 `/chat/personal/` 后，先确认文字聊天和原会话历史正常，再手动启用麦克风。浏览器麦克风来源是客户端，不一定是树莓派 USB 设备。用户点击录音/听写才会通过该服务上传到 DashScope；本轮没有自动录制或再次上传语音。Stop reading 停止播放；Talk Stop 是否正确取消实际聊天轮次仍需要真实浏览器验收。

部署验证仅包括镜像内 3 项模拟测试、原生 schema 校验、服务健康 200 和配置差异检查；先前单次合成 ASR 验证不能代替此适配器的真实浏览器端到端测试。当前未宣称浏览器 Talk、回声消除或完整打断体验已经验收。

本次检查发现重启后 API 实际 IP 已从 `172.21.0.15` 变成 `172.21.0.16`，personal 原生 UI 因旧的单地址 `gateway.trustedProxies` 返回 403。只将 personal 精确信任地址替换为实际 API 地址后，HTTPS `/chat/personal/` 返回 200；token 认证模式与 token 未改变，没有信任整个网段或同步修改其他角色。今后容器 IP 变化时必须重新核对实际上游地址，不应把关闭认证当成修复。

回滚时先停对应部署的 `agent-speech`（迁移前容器名为 `personal-speech`）。personal 的配置恢复点保存在私有 `agent-homes/personal/voice/openclaw-before-*.json`；恢复前核对其后的用户变更，只撤销本次 speech 配置，勿直接用旧文件覆盖新模型或渠道配置。该试点不要求重建八个 Agent，也不要求部署此前尚未上线的 ROS/API/UI 语音改动。

### Talk 出现 “OpenClaw tool call aborted”

这条信息来自原生前端等待 Agent 回复时的取消分支，不等于 ASR/TTS 鉴权失败。2026-11-15 实际排查中，转写后出现 `talk.session.close`、同一 run 的 `chat.abort` 和 `run aborted / AbortError`；用户确认在等待时点击了 Stop 或再次点麦克风，属于主动结束 Talk。

使用 Talk 时，启动后等正在监听，再说短句；说完停顿，让系统自动识别并提交，然后等待回复。**不要用 Stop 或再次点麦克风来表示“说完了”**，它会结束 Talk，并可能取消当前尚未完成的聊天轮次。需要停止采集、播放或生成时再用 Stop；只想手动结束录音而保留待发文字时，应使用独立听写/发送流程，不把 Talk Stop 当作提交键。

如果没有点击 Stop、切换页面或刷新仍出现 aborted，再按同一 run ID 核对前端取消、连接丢失、超时及 Gateway 生命周期；不要直接放宽认证、扩大超时或更换 provider。此处说明的是一次主动取消的已确认原因，不代表 Talk 自动回复已经重新验收通过。

### Personal TTS 403 修复与浏览器验收

2026-11-15 的固定短句对照测试：personal 安装包的 `node-edge-tts@1.2.10` 直接调用返回 403，同一 Docker 网络中的 Python `edge-tts@7.2.7` 也握手失败，而 `edge-tts@7.3.1` 成功；系统 NTP 同步且与 Microsoft HTTP 日期一致。这支持客户端协议兼容问题，不应仅凭 403 认定缺少 Microsoft key 或余额不足。

共享 `agent-speech` 镜像固定安装 `edge-tts==7.3.1`，提供 `/v1/audio/speech` 音频接口。请求需本地专用 token，固定模型名 `local-edge`、音色 `zh-CN-XiaoxiaoNeural`、MP3 格式，最长 1000 字符、音频不超过 3 MiB、合成超时 30 秒，与 ASR 共用单路并发上限。TTS provider 标为 `openai` 仅代表兼容协议：新配置使用 `tts.providers.openai.baseUrl=http://agent-speech:18081/v1`（旧部署为兼容别名 `personal-speech`），实际仍是 Edge 中文语音，不调用 OpenAI 云端；旧 Microsoft 路由禁用回退。通用 `models.providers.openai` 和原聊天模型没有改变。

准备本地 TTS 配置批次（目标必须是新文件，文件中含本地 token，不可公开）：

```bash
python3 panopticon/tools/agent_speech.py prepare-tts-config \
	--client panopticon/agent-homes/personal/voice/speech-client.json \
	--credentials panopticon/agent-homes/personal/voice/tts-batch-NEW.json

docker exec --user node openclaw-personal openclaw config set \
	--batch-file /home/node/.openclaw/voice/tts-batch-NEW.json --dry-run
```

校验后再明确应用同一批次，保留私有 `openclaw-before-tts-*.json` 恢复点；无需重启 Agent。历史试点发布镜像为 `personal-speech:tts-20261115-091551`，旧镜像 `personal-speech:rollback-20261115-091551` 保留，这些实际历史标签不因源码改名而改写。新构建使用 `Dockerfile.agent-speech` 和 `agent-speech:local`。回滚时应同时核对 TTS 路由与服务镜像，不能只换旧镜像而留下不可用的新接口。

验证结果：镜像内 6 项模拟认证/契约测试通过，固定句接口 HTTP 200，返回 17568 字节 MP3；原生 UI Read aloud 的 403 消失，用户确认听到语音，并在播放中点击 Stop reading 后确认声音立即中断；页面恢复 Read aloud、无 TTS 错误，麦克风保持停止。八个 Agent 容器启动基线未变，只更新独立语音服务和 personal 的 TTS 配置。

此前真实语音转写将“你好，这是语音识别测试”识别成了其他文本；这项准确性仍未重新通过。初次语音按钮实际启动 Talk 并自动提交转写，不是仅写入草稿的 Dictation。本次验证了手动 Read aloud 和播放中 Stop，不等于已重新验证 Talk 自动语音回复、回声消除或连续对话。

当前项目的 Chat 面板继续嵌入 OpenClaw 原生 WebChat，不另建会话或转录存储。OpenClaw 2026.11.3 的 WebChat 支持文字输入和按住麦克风听写到当前会话；配置好转写与 TTS 后，可使用 Talk 并在停止时取消当前聊天轮次。UI iframe 已声明麦克风权限；浏览器仍要求 HTTPS/localhost、用户授予权限及可用的语音 provider。听写是否有实时部分字幕取决于 provider。

原生 WebChat 的转写使用 `tools.media.models` 或 `agents.defaults.voiceModel` 等 OpenClaw 配置；Talk 还需要转写与语音输出配置。此前八角色均未配置这些能力；目前仅 personal 按上述试点配置，其他角色保持不变。不要把 ASR/TTS API key 加入 UI、README 或提交的 env example；按每个 Agent 的 credential/provider 约定单独配置。当前 P1 复用原生聊天，因此打字和听写使用同一 Agent 会话与聊天历史；不需要再经过 ROS 语音命令入口。

ROS 实体设备链路是独立入口，按下述规则使用稳定 `device_id`；它不自动与浏览器会话共享麦克风音频或播放控制。

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

- `MC_VOICE_TTS_FEEDBACK_ENABLED=1`
开启语音直控后的播报反馈事件。它只表示 Mission Control 已生成 `voice.tts.requested` 播报请求；真实发声仍取决于设备侧或后续下行桥接是否消费这个事件。

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
仅兼容旧版纯文本 TTS 状态的 speaking 回 idle 兜底。新 JSON 生命周期事件以播放器实际 finished/cancelled 状态为准。

- `MC_VOICE_DEVICE_ID=desk-pi`
为这套语音桥接和配对 ROS 音频设备设置稳定且唯一的 ID。桥接器、`run_humble_container.sh` 启动的音频栈必须一致；没有 ID 或 TTS 请求没有匹配 ID 时，默认不播报。不同设备不可共用 ID。

- `MC_VOICE_BRIDGE_LOG_PAYLOAD=1`
只在排障时临时打开，平时建议保持 `0`。

设备播报消费者会将已确认事件游标保存在 ROS 容器挂载的 `~/.local/state/openclaw-voice/tts-cursor.sqlite3`，数据库权限为 600、目录权限为 700；可用 `MC_VOICE_STATE_DIR` 指定主机持久目录。首次启动先记录当前 feed 历史，不重播旧播报；尚未收到设备终态的请求不会确认，重启后可重投。若要更换设备身份，应为新设备使用新的 cursor DB。

## 真实设备侧需要对齐什么

桥接器当前订阅的就是 4 类 ROS2 话题：

- `wakeup`，类型 `std_msgs/msg/Bool`
- `asr`，类型 `std_msgs/msg/String`
- `text_response`，类型 `std_msgs/msg/String`
- `tts_topic`，类型 `std_msgs/msg/String`
- `tts_cancel`，类型 `std_msgs/msg/String`，内容为 `request_id` 或 `{"request_id":"..."}`

桥接逻辑如下：

- `wakeup=true`：写 `voice.state = listening`
- `asr` 文本：写 `voice.asr.final`，同时切 `voice.state = thinking`
- `text_response`：写 `voice.llm.first_token`
- `tts_topic`：新版本以 JSON 状态上报 queued/started/finished/failed/cancelled；桥接器据真实播放状态更新 UI，不再对新状态使用固定时长推断

如果你的设备侧命名不同，有两种方式：

1. 改设备侧发布的话题名。
2. 改 `mission-control-voice-bridge.env` 中的 `MC_VOICE_TOPIC_*`。

ASR 事件和语音命令回执携带 `device_id`，feed 消费器只把定向给本设备的 TTS 请求送入有界串行队列；重复 request_id 会被去重。可通过 `tts_cancel` 取消排队或当前请求，系统会尝试终止对应播放/合成进程。取消协议是 ROS 设备侧能力，不等同于 OpenClaw WebChat 的会话 Stop。

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
- 如果开启播报反馈，还会看到 `voice.tts.requested`

如果命令被拒绝，会看到：

- `voice.command.rejected`
- 如果开启播报反馈，还会看到带简短失败原因的 `voice.tts.requested`

## 看到什么算联调成功

最低成功标准：

1. 说唤醒词后，feed 里出现 `voice.state(listening)`。
2. 说一句普通话后，feed 里出现 `voice.asr.final`。
3. 如果设备侧已经打通播报，feed 里出现 `voice.tts.start`。
4. 如果开启语音直控，说一条带前缀命令后，Mission Control 任务板或 feed 发生对应变化。
5. 如果开启播报反馈，feed 里出现 `voice.tts.requested`，其中 `payload.text` 是可播报的执行或拒绝摘要。

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