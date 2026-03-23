# 新手也能读懂的 openclaw.json 配置文件使用说明

> 适用对象：第一次接触 OpenClaw、Panopticon、Mission Control 的用户
>
> 文档目标：看懂 `openclaw.json` 在做什么，知道哪些字段能改、哪些字段尽量别动，尤其能正确配置本地 `Ollama`

---

## 1. 先知道：`openclaw.json` 是干什么的？

`openclaw.json` 是 OpenClaw 的核心运行配置。

它决定了几件事：

- 用哪个模型
- 模型从哪里调用
- 聊天消息从哪个渠道进入
- OpenClaw 网关监听哪个端口
- 工作目录在哪里
- 是否启用插件、浏览器、记忆等能力

如果把 OpenClaw 比作一台车，`openclaw.json` 就是这台车的“总控制面板”。

---

## 2. 配置文件通常放在哪里？

这取决于你的运行方式。

### 单机/普通本地安装

常见位置：

- Windows：`C:\Users\你的用户名\.openclaw\openclaw.json`
- Linux/macOS：`~/.openclaw/openclaw.json`

### 本仓库当前的 Panopticon 多 Agent 部署

本项目不是单个全局配置，而是**每个 Agent 各有一份配置**。

例如：

- `nox` 的配置在 [panopticon/agent-homes/nox/openclaw.json](panopticon/agent-homes/nox/openclaw.json)
- `growth` 的配置在 [panopticon/agent-homes/growth/openclaw.json](../panopticon/agent-homes/growth/openclaw.json)
- `personal` 的配置在 [panopticon/agent-homes/personal/openclaw.json](../panopticon/agent-homes/personal/openclaw.json)

也就是说，你改哪个 Agent，就改它自己的 `openclaw.json`。

---

## 3. 改乱了怎么办？

可以先试：

```bash
openclaw doctor --fix
```

它会修一部分常见配置问题，比如：

- 结构不规范
- 某些单账户字段位置不对
- 缺少部分默认项

但要注意：

- 它不会帮你“猜”正确模型参数
- 它也不会替你填好真实的 `apiKey`

在本仓库的 Panopticon 场景里，如果是容器中的 Agent 配置有变更，通常还需要重启对应容器，例如：

```bash
docker restart openclaw-nox
```

---

## 4. 先记住：新手最常改的只有 5 块

对大多数用户，最重要的是这 5 个部分：

1. `models`
2. `agents.defaults.model`
3. `agents.defaults.workspace`
4. `channels`
5. `gateway`

其他字段像 `meta`、`update`、`messages.tts`、`plugins.installs`，通常先不用碰。

---

## 5. 顶层字段到底是什么意思？

下面按“新手能看懂”的方式解释。

### `meta`

系统自动记录配置最近一次被哪个版本触碰。

一般不用手改。

示例：

```json
"meta": {
  "lastTouchedVersion": "2026.3.1",
  "lastTouchedAt": "2026-03-03T14:48:05.519Z"
}
```

---

### `update`

控制是否在启动时检查更新。

示例：

```json
"update": {
  "checkOnStart": false
}
```

含义：

- `true`：启动时检查更新
- `false`：不检查

---

### `browser`

配置 OpenClaw 调用浏览器时的行为。

例如：

```json
"browser": {
  "executablePath": "/usr/bin/chromium",
  "headless": true,
  "noSandbox": true,
  "defaultProfile": "openclaw"
}
```

重点理解：

- `executablePath`：浏览器程序路径
- `headless`：是否无界面运行
- `defaultProfile`：默认浏览器配置名

如果你只是先把聊天跑起来，这块通常也不用先动。

---

## 6. 最重要：`models` 是模型总目录

这是最容易改，也最容易改错的部分。

结构长这样：

```json
"models": {
  "mode": "merge",
  "providers": {
    "default": { ... },
    "ollama": { ... }
  }
}
```

### `models.mode`

- `merge`：保留已有模型目录，再加上你自定义的 provider
- `replace`：只用你配置的这些模型

新手建议先用：

```json
"mode": "merge"
```

---

### `models.providers`

这里定义“模型服务商列表”。

一个 provider 可以是：

- OpenAI
- Claude
- GLM
- 自建代理
- 本地 `Ollama`

#### 本仓库当前常见的两类 provider

1. 远程兼容接口 provider，例如：

```json
"default": {
  "baseUrl": "https://example.com/v1",
  "apiKey": "你的密钥",
  "api": "openai-completions",
  "models": [ ... ]
}
```

2. 本地 `Ollama` provider，例如：

```json
"ollama": {
  "baseUrl": "http://192.168.1.3:11434",
  "apiKey": "ollama-local",
  "api": "ollama",
  "models": [ ... ]
}
```

---

## 7. `models.providers.*` 里的常见字段说明

### `baseUrl`

模型服务地址。

例子：

- 远程服务：`https://api.openai.com/v1`
- 本地 Ollama：`http://192.168.1.3:11434`

### `apiKey`

访问密钥。

注意：

- 真正的密钥不要提交到 Git
- 发截图或分享配置时一定要打码
- `Ollama` 本地模式通常不需要真实密钥，常用占位值：`ollama-local`

### `api`

告诉 OpenClaw“该按什么协议跟上游说话”。

常见值：

- `openai-completions`
- `ollama`

### `models`

就是这个 provider 下可选模型列表。

---

## 8. 单个模型条目怎么理解？

一个模型通常像这样：

```json
{
  "id": "qwen3.5:2b",
  "name": "qwen3.5:2b",
  "reasoning": false,
  "input": ["text"],
  "cost": {
    "input": 0,
    "output": 0,
    "cacheRead": 0,
    "cacheWrite": 0
  },
  "contextWindow": 16000,
  "maxTokens": 4096
}
```

各字段含义：

- `id`：真正引用模型时使用的名字
- `name`：显示名，通常可和 `id` 一样
- `reasoning`：是否把它当作“推理型模型”看待
- `input`：支持什么输入，常见是 `text` 或 `text + image`
- `cost`：费用信息，本地模型一般都填 `0`
- `contextWindow`：上下文窗口大小
- `maxTokens`：单次输出长度上限

---

## 9. 新手最容易踩坑：本地 Ollama 怎么写才对？

如果你已经启动了 `Ollama`，并且已经下载了：

- `qwen3.5:2b`

那推荐写法是：

```json
"ollama": {
  "baseUrl": "http://192.168.1.3:11434",
  "apiKey": "ollama-local",
  "api": "ollama",
  "models": [
    {
      "id": "qwen3.5:2b",
      "name": "qwen3.5:2b",
      "reasoning": false,
      "input": ["text"],
      "cost": {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0
      },
      "contextWindow": 16000,
      "maxTokens": 4096
    }
  ]
}
```

### 这里要特别注意 4 件事

#### 1）`ollama` 必须写在 `models.providers` 里面

正确：

```json
"models": {
  "providers": {
    "ollama": { ... }
  }
}
```

错误：

```json
"models": {
  "providers": { ... },
  "ollama": { ... }
}
```

#### 2）`api` 应写成 `ollama`

推荐：

```json
"api": "ollama"
```

不推荐再写成：

```json
"api": "openai-completions"
```

#### 3）`baseUrl` 不要加 `/v1`

正确：

```json
"baseUrl": "http://192.168.1.3:11434"
```

不建议：

```json
"baseUrl": "http://192.168.1.3:11434/v1"
```

#### 4）`qwen3.5:2b` 的上下文别乱写太大，也别写太小

本仓库实际测试过：

- `8192`：会被 OpenClaw 判定过小，直接回退
- `262144`：会把内存打爆，触发 `Ollama API error 500`
- `16000`：当前机器上可用

所以新手先用：

```json
"contextWindow": 16000
```

更稳。

---

## 10. `agents.defaults`：默认行为配置

这块是“默认使用哪个模型、工作目录在哪、并发多少”。

示例：

```json
"agents": {
  "defaults": {
    "models": {
      "ollama/qwen3.5:2b": {
        "alias": "qwen-local",
        "params": {
          "think": false
        }
      }
    },
    "model": {
      "primary": "ollama/qwen3.5:2b",
      "fallbacks": ["default/glm-4.7"]
    },
    "workspace": "/home/node/.openclaw/workspace",
    "compaction": {
      "mode": "safeguard"
    },
    "maxConcurrent": 4,
    "subagents": {
      "maxConcurrent": 8
    }
  }
}
```

### 重点字段

#### `model.primary`

默认主模型。

格式固定是：

```text
provider/model
```

例如：

- `ollama/qwen3.5:2b`
- `default/glm-4.7`

#### `model.fallbacks`

当主模型失败时，自动尝试备用模型。

如果你希望**彻底只用本地模型**，可以去掉这部分，避免回退到远程模型。

#### `agents.defaults.models`

这是模型别名和模型参数区。

比如：

```json
"ollama/qwen3.5:2b": {
  "alias": "qwen-local",
  "params": {
    "think": false
  }
}
```

含义：

- `alias`：给模型起个短名字
- `params`：给这个模型附加默认参数

---

## 11. 关闭 `qwen3.5:2b` 思考模式怎么写？

如果你发现模型回复很慢，或者不断出现 Thinking 过程，可以在：

```json
"agents": {
  "defaults": {
    "models": {
      "ollama/qwen3.5:2b": {
        "params": {
          "think": false
        }
      }
    }
  }
}
```

这就是告诉 OpenClaw：

- 调用 `qwen3.5:2b` 时默认关闭 thinking

对当前机器，这个设置很有必要。

---

## 12. `imageModel` 是什么？

`imageModel` 是“看图模型”。

如果主模型不支持图片输入，OpenClaw 会在处理图片时改用它。

例如：

```json
"imageModel": {
  "primary": "default/glm-4.7"
}
```

如果你现在只做文本聊天，这块先不动也行。

---

## 13. `workspace` 是什么？

这是 AI 能读写的工作目录。

例如：

```json
"workspace": "/home/node/.openclaw/workspace"
```

意义很简单：

- AI 在哪里读文件
- AI 在哪里写文件
- 记忆、草稿、临时输出通常围绕这里展开

如果路径不对，很多工具就会表现异常。

---

## 14. `messages`

控制消息层行为。

当前最常见的是：

```json
"messages": {
  "ackReactionScope": "group-mentions"
}
```

含义：

- 在群里被提及时，先做一个确认反应

对新手来说，先知道它不是模型配置就够了。

---

## 15. `commands`

控制 OpenClaw 聊天命令行为，比如：

- `/model`
- `/restart`
- `/help`

示例：

```json
"commands": {
  "native": "auto",
  "nativeSkills": "auto",
  "restart": true,
  "ownerDisplay": "raw"
}
```

一般先保留默认即可。

---

## 16. `channels`：消息渠道配置

这块控制 OpenClaw 从哪里收消息。

本仓库最常见的是 `feishu`。

示例：

```json
"channels": {
  "feishu": {
    "enabled": true,
    "dmPolicy": "open",
    "groupPolicy": "open",
    "accounts": {
      "main": {
        "appId": "你的 AppID",
        "appSecret": "你的 AppSecret",
        "botName": "OpenClaw Bot"
      }
    },
    "connectionMode": "websocket",
    "domain": "feishu",
    "requireMention": true,
    "groupSessionScope": "group"
  }
}
```

### 新手要理解的字段

- `enabled`：是否启用该渠道
- `accounts.main`：该渠道的主账号配置
- `appId` / `appSecret`：渠道凭据
- `requireMention`：群聊里是否必须 @ 机器人
- `dmPolicy` / `groupPolicy`：私聊/群聊允许策略

注意：

- 这类密钥不要发群、不要传 Git、不要截图明文展示

---

## 17. `gateway`：OpenClaw 网关核心配置

这一块决定 OpenClaw 服务怎么暴露出来。

例子：

```json
"gateway": {
  "port": 26216,
  "mode": "local",
  "bind": "lan",
  "controlUi": {
    "allowedOrigins": [
      "http://127.0.0.1:18920",
      "http://localhost:18920"
    ],
    "allowInsecureAuth": true,
    "dangerouslyDisableDeviceAuth": true
  },
  "auth": {
    "token": "请改成你的 token",
    "mode": "token"
  },
  "trustedProxies": [
    "172.21.0.0/16",
    "172.21.0.6"
  ]
}
```

### 重点解释

- `port`：监听端口
- `mode`：运行模式
- `bind`：绑定地址
- `auth.mode`：认证方式
- `auth.token`：访问令牌
- `trustedProxies`：可信反向代理列表

### 新手建议

如果你不是在做反代、多容器、局域网控制台联动，先不要乱改这块。

因为一旦改错，可能出现：

- 页面打不开
- 认证失效
- 外网暴露风险

---

## 18. `memory`

控制记忆后端。

本仓库常见的是 `qmd`：

```json
"memory": {
  "backend": "qmd",
  "qmd": {
    "command": "/usr/local/bin/qmd",
    "paths": [
      {
        "path": "/home/node/.openclaw/workspace",
        "name": "workspace",
        "pattern": "**/*.md"
      }
    ]
  }
}
```

如果 `qmd` 程序不存在，日志里会看到 `ENOENT` 警告。

这不一定会让聊天主流程挂掉，但会影响记忆功能。

---

## 19. `plugins`

控制插件启停。

例如：

```json
"plugins": {
  "entries": {
    "feishu": {
      "enabled": true
    }
  },
  "installs": {}
}
```

新手先知道：

- `entries`：插件是否启用
- `installs`：通常是安装元数据

如果你没在折腾扩展插件，先别改。

---

## 20. 一个适合新手的最小可用思路

如果你只是要先跑通本地 `Ollama + qwen3.5:2b`，只需要确保这几件事：

### 第一步：模型 provider 正确

```json
"models": {
  "mode": "merge",
  "providers": {
    "ollama": {
      "baseUrl": "http://192.168.1.3:11434",
      "apiKey": "ollama-local",
      "api": "ollama",
      "models": [
        {
          "id": "qwen3.5:2b",
          "name": "qwen3.5:2b",
          "reasoning": false,
          "input": ["text"],
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          },
          "contextWindow": 16000,
          "maxTokens": 4096
        }
      ]
    }
  }
}
```

### 第二步：默认模型切过去

```json
"agents": {
  "defaults": {
    "models": {
      "ollama/qwen3.5:2b": {
        "alias": "qwen-local",
        "params": {
          "think": false
        }
      }
    },
    "model": {
      "primary": "ollama/qwen3.5:2b"
    }
  }
}
```

### 第三步：重启生效

普通安装常见用法：

```bash
openclaw gateway restart
```

本仓库 Panopticon 场景更常见的是：

```bash
docker restart openclaw-nox
```

---

## 21. 新手最常见错误清单

### 错误 1：把 `ollama` 写错层级

错误：写到 `models.ollama`

正确：写到 `models.providers.ollama`

### 错误 2：把 `api` 写成旧兼容模式

不建议：

```json
"api": "openai-completions"
```

推荐：

```json
"api": "ollama"
```

### 错误 3：`baseUrl` 还写 `127.0.0.1`

如果 OpenClaw 跑在容器里，`127.0.0.1` 常常指向容器自己，不是宿主机。

所以容器化场景要写成容器可达地址，例如局域网 IP：

```json
"baseUrl": "http://192.168.1.3:11434"
```

### 错误 4：上下文窗口太小

日志会提示：

```text
Model context window too small (8192 tokens). Minimum is 16000.
```

### 错误 5：上下文窗口太大

日志会提示：

```text
Ollama API error 500: model requires more system memory
```

### 错误 6：明明是本地模型失败，却看到远程限流

这通常是因为：

1. 本地主模型先失败
2. OpenClaw 自动回退到远程模型
3. 远程模型再报 `rate limit`

所以看到远程限流，不一定说明问题在远程 provider 本身。

---

## 22. 安全提醒

下面这些字段要重点小心：

| 配置项 | 风险 | 建议 |
| --- | --- | --- |
| `apiKey` | 高 | 不要公开，不要提交 Git |
| `appSecret` | 高 | 不要截图明文发群 |
| `gateway.auth.token` | 高 | 不要泄露 |
| `gateway.bind` | 中 | 不懂就别随便改成公网暴露 |
| `allowInsecureAuth` | 高 | 只在明确知道风险时使用 |
| `dangerouslyDisableDeviceAuth` | 高 | 只在受控环境中使用 |

---

## 23. 常用命令

### 校验配置

```bash
openclaw config validate
```

### 修复部分配置问题

```bash
openclaw doctor --fix
```

### 查看模型状态

```bash
openclaw models status
```

### 查看模型列表

```bash
openclaw models list
```

### 普通安装重启 gateway

```bash
openclaw gateway restart
```

### Panopticon 中重启某个 Agent

```bash
docker restart openclaw-nox
```

---

## 24. 给新手的最后建议

第一次改 `openclaw.json`，只改这几项就够了：

1. `models.providers`
2. `agents.defaults.model.primary`
3. `agents.defaults.models["provider/model"].params`
4. `agents.defaults.workspace`
5. `channels.feishu.accounts.main`

其他部分能不动就先不动。

最怕的不是“字段多”，而是“还没理解层级就乱改”。

如果你按本文顺序理解：

- 先知道文件位置
- 再知道模型在哪配
- 再知道默认模型在哪改
- 最后才碰渠道和网关

基本就不会乱。

---

## 25. 本文对应的仓库场景

本文内容优先对应当前仓库的实际部署方式：

- Panopticon 多 Agent
- 每个 Agent 各有自己的 `openclaw.json`
- 已验证本地 `Ollama + qwen3.5:2b`
- 已验证 `think: false` 可关闭思考模式
- 已验证当前机器上 `contextWindow: 16000` 可用

如果你的部署方式不同，可以把本文当作“理解结构”的入门版本，而不是死记硬背每个值。

---

**文档版本**：1.1  
**适合人群**：OpenClaw / Panopticon 新手用户  
**最后更新**：2026-03-21