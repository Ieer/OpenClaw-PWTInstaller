# OpenClaw ROS2 Audio

`openclaw-ros2-audio` 是接入 OpenClaw / Mission Control 的 ROS2 语音栈工作区。它负责把真实麦克风、ASR、TTS 组件转换为当前 Mission Control 语音桥接器已经支持的 ROS2 话题。

## 接口契约

当前 Mission Control 语音桥接器订阅以下话题：

| 话题 | 类型 | 方向 | 作用 |
| --- | --- | --- | --- |
| `/wakeup` | `std_msgs/msg/Bool` | 语音栈 -> Mission Control | `true` 表示进入 listening |
| `/asr` | `std_msgs/msg/String` | 语音栈 -> Mission Control | 最终识别文本，触发 `voice.asr.final` |
| `/text_response` | `std_msgs/msg/String` | 可选 | 首个文本响应 token，触发 `voice.llm.first_token` |
| `/tts_topic` | `std_msgs/msg/String` | 语音栈 -> Mission Control | 开始播报，触发 `voice.tts.start` |
| `/tts_request` | `std_msgs/msg/String` | 本语音栈内部 | Mission Control TTS 反馈转本地播报 |

## 包结构

- `wake_node`：发布唤醒事件。
- `asr_node`：收到唤醒后录音、识别并发布最终文本。
- `tts_node`：订阅 `/tts_request`，执行播报并发布 `/tts_topic`。
- `mc_tts_feedback_node`：轮询 Mission Control `voice.tts.requested`，转发到 `/tts_request`。
- `manual_turn_node`：无硬件 smoke 节点，手动发布一轮 wake/asr/tts。

## 构建

在安装 ROS2 Humble 与 `colcon` 后：

```bash
cd external/openclaw-ros2-audio
python3 -m pip install -r requirements.txt
colcon build --symlink-install
source install/setup.bash
```

### 推荐：使用 `ros:humble-ros-base` 容器

Debian / Raspberry Pi OS 上不建议直接混用 Ubuntu Jammy 的 ROS2 apt 源。可以直接使用仓库脚本在 `ros:humble-ros-base` 容器内构建和运行：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml --profile voice up -d mission-control-voice-bridge
bash external/openclaw-ros2-audio/scripts/run_humble_container.sh
```

脚本会：

- 复用 `mission-control-voice-bridge` 的网络命名空间，方便 ROS2 DDS 发现。
- 默认设置 `FASTDDS_BUILTIN_TRANSPORTS=UDPv4`，避免跨容器共享内存传输导致“发现订阅但收不到消息”。
- 只读挂载当前工作区源码，并在容器 `/tmp` 内构建，避免宿主机生成 root-owned 构建产物。
- 默认复用镜像内已有 `colcon` / `python3-yaml`，避免每次访问 Ubuntu apt 源；只有缺失时才安装基础构建依赖。
- 设置 `OPENCLAW_ASR_HTTP_URL`、`OPENCLAW_ASR_HTTP_TOKEN`、`OPENCLAW_AUDIO_INPUT_DEVICE`、`OPENCLAW_TTS_VOICE` 等环境变量透传。
- 自动挂载 `/dev/snd`；检测到 PulseAudio / PipeWire socket 时会透传 `PULSE_SERVER`，否则回退到 ALSA。
- 默认运行 `manual_turn_node` 发布一轮 `/wakeup`、`/asr`、`/tts_topic`。

如果要在容器内真实播放 TTS，可额外启用音频依赖安装：

```bash
OPENCLAW_ROS_INSTALL_AUDIO_DEPS=1 \
bash external/openclaw-ros2-audio/scripts/run_humble_container.sh \
	ros2 launch openclaw_voice_stack openclaw_voice_stack.launch.py
```

如需启动完整 launch：

```bash
bash external/openclaw-ros2-audio/scripts/run_humble_container.sh \
	ros2 launch openclaw_voice_stack openclaw_voice_stack.launch.py
```

### 真实麦克风 + HTTP ASR + edge-tts

第一阶段真实硬件链路推荐走轻量方案：容器内录音，调用外部 HTTP ASR 服务，Mission Control 生成反馈后由 edge-tts 播放。这样不把 SenseVoice / Kokoro 等重模型依赖直接塞进 ROS2 容器。

HTTP ASR 服务契约：

- 请求体：WAV bytes。
- `Content-Type`: `application/octet-stream`。
- 额外 header：`X-Audio-Sample-Rate`、`X-ASR-Language`。
- 可选鉴权：`Authorization: Bearer $OPENCLAW_ASR_HTTP_TOKEN`。
- 返回 JSON 字段支持 `text`、`transcript` 或 `result.text`。

启动真实设备配置：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml --profile voice up -d mission-control-voice-bridge
export OPENCLAW_ASR_HTTP_URL="http://<asr-host>:<port>/<path>"
export OPENCLAW_AUDIO_INPUT_DEVICE=""  # 留空使用 ALSA 默认麦克风；也可填 plughw:1,0 等
export OPENCLAW_AUDIO_OUTPUT_DEVICE="" # 留空使用 ALSA 默认扬声器；也可填 plughw:CARD=Device,DEV=0 等
export OPENCLAW_TTS_VOICE="zh-CN-XiaoyiNeural"
bash external/openclaw-ros2-audio/scripts/run_real_device_container.sh
```

使用通义千问 / DashScope Paraformer 时，`run_real_device_container.sh` 默认会在 ROS2 容器内启动一个本地 HTTP ASR 包装服务，并自动把 `OPENCLAW_ASR_HTTP_URL` 设为 `http://127.0.0.1:18081/asr`。可通过环境变量直接传入密钥，或从 Yahboom 的配置文件读取；密钥不会写入本仓库：

```bash
export YAHBOOM_TONGYI_CONFIG=/home/pi/yahboom_ws/src/largemodel/config/large_model_interface.yaml
# 或改用：export DASHSCOPE_API_KEY="..."
bash external/openclaw-ros2-audio/scripts/run_real_device_container.sh
```

包装服务会读取 `tongyi_api_key`、`oline_asr_model` 和 `oline_asr_sample_rate`，默认模型为 `paraformer-realtime-8k-v2`，默认采样率为 `16000`。

首期配置文件是 `src/openclaw_voice_stack/config/real-device.http-edge.example.yaml`。它默认：

- `asr_node` 使用 `http` engine。
- `tts_node` 使用 `edge` engine。
- `wake_node` 使用 `manual` mode。硬件验收时，可先在另一终端发布 `/wakeup=true` 后对麦克风说话；第二阶段再接 Yahboom / CLB 串口唤醒。

硬件音频评估：

```bash
OPENCLAW_ROS_INSTALL_AUDIO_DEPS=1 \
bash external/openclaw-ros2-audio/scripts/run_humble_container.sh \
	bash scripts/assess_audio_hardware.sh

OPENCLAW_ROS_INSTALL_AUDIO_DEPS=1 \
OPENCLAW_AUDIO_PROBE_TTS=1 \
bash external/openclaw-ros2-audio/scripts/run_humble_container.sh \
	bash scripts/assess_audio_hardware.sh
```

如果后续要接 Yahboom / CLB 串口唤醒，可设置：

```bash
OPENCLAW_ROS_SERIAL_DEVICES="/dev/ttyUSB0 /dev/ttyUSB1" \
bash external/openclaw-ros2-audio/scripts/run_real_device_container.sh
```

当前脚本只做设备映射；串口唤醒节点将在第二阶段增加。

#### Yahboom 配置对比后的优化点

对比 `/home/pi/yahboom_ws/src/largemodel/config/yahboom.yaml` 后，当前真实设备配置采用这些折中值：

- `cooldown_ms: 2000`：对应 Yahboom 的 2 秒唤醒去抖，降低 TTS 回声或环境噪声重复触发。
- `wakeup_record_delay_ms: 400`：唤醒后延迟开录，避免把唤醒提示音、蜂鸣声或扬声器尾音录入 ASR。
- `sample_rate: 16000`：HTTP ASR payload 默认固定 16 kHz；Yahboom 常见做法是设备侧 48 kHz 采集后转 16 kHz。若你的麦克风只稳定支持 48 kHz，优先用 ALSA `plug` 设备做重采样。
- `max_utterance_seconds: 6.0`：第一阶段仍是固定时长录音，比 smoke 配置略长；等链路稳定后再导入 Yahboom 风格的 WebRTC VAD 端点检测。
- `poll_interval_seconds: 0.5`：Mission Control TTS 反馈轮询更快，减少 `voice.tts.requested` 到本地播报的等待。

Yahboom 的 `model_service` 同时负责 LLM、TTS、摄像头、工具调用和历史状态；OpenClaw 中这些职责由 Mission Control 承担，因此不直接迁移该节点。

## 最小 smoke

```bash
source external/openclaw-ros2-audio/install/setup.bash
ros2 run openclaw_voice_stack manual_turn_node
```

同时在另一个终端观察：

```bash
ros2 topic echo /asr
```

## 与 Mission Control 联调

先启动当前仓库已有 bridge：

```bash
docker compose -f panopticon/docker-compose.panopticon.yml --profile voice up -d mission-control-voice-bridge
```

再启动本语音栈：

```bash
source external/openclaw-ros2-audio/install/setup.bash
ros2 launch openclaw_voice_stack openclaw_voice_stack.launch.py
```

验证 live 链路：

```bash
bash panopticon/tools/check_voice_bridge_live.sh
```

## 引擎策略

第一版优先跑通链路：

- ASR 默认 `dummy`，可切换到 `http` 或 `vosk`。
- TTS 默认 `espeak`，可切换到 `edge` 或 `piper`。
- 在线服务的密钥只从环境变量读取，不写入 YAML。
- Yahboom 语音栈可作为硬件驱动参考：优先吸收串口 KWS、`pyaudio`、`webrtcvad`、PulseAudio/ALSA fallback；不直接迁移其大模型服务，避免与 Mission Control 的任务、上下文和反馈流重叠。

## 注意

- 工作区的 `build/`、`install/`、`log/` 是本地构建产物，不提交。
- 模型、录音样本、API key 不提交。
- 树莓派上建议先用 `manual_turn_node` 和 `dummy` 引擎验收链路，再接真实模型。
