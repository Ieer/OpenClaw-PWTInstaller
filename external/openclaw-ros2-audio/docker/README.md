# Docker runtime placeholder

第一阶段优先宿主机运行 ROS2 语音栈，避免先卡在声卡、DDS、组播和权限问题。

后续容器化时需要处理：

- `/dev/snd` 挂载
- `audio` group 权限
- ALSA 或 PulseAudio socket
- host network 或明确的 ROS2 DDS 配置
- 模型目录只读挂载
- API token 通过 env 注入
