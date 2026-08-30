# 编程智能体（coding agent）

一个基于大语言模型（DeepSeek）的自主编程智能体：它能自主地**读写文件、执行命令**，循环迭代直到完成你交给它的编程任务——类似一个简化版 Claude Code / Codex / DeepSeek Harness。

> 项目定位：**所有重要逻辑自研**，仅使用 `openai` 官方客户端库访问 DeepSeek 的 OpenAI 兼容接口。不使用任何 agent 框架 / SDK（LangChain、LlamaIndex、Agent SDK 等），不依赖任何服务端托管的代码执行或文件工具。

---

## 目录

- [特性](#特性)
- [快速开始](#快速开始)
- [使用示例](#使用示例)
- [配置项](#配置项)
- [架构与设计决策](#架构与设计决策)
- [工具清单](#工具清单)
- [循环终止条件](#循环终止条件)
- [测试](#测试)
- [安全说明](#安全说明)
- [项目结构](#项目结构)

---

## 特性

- **完整 agent 循环**：`思考 → 行动 → 观察` 反复迭代，直到模型给出最终回答或调用 `finish` 工具。
- **多轮会话记忆**：交互模式下后续输入沿用同一会话（agent 记住之前的上下文）。
- **会话持久化**：每轮自动落盘；`/save` 命名保存、`/resume`（或 `/switch`）恢复、`/sessions` 列出、`/clear` 清空，会话可跨进程恢复。
- **自研工具系统**：9 个工具（读文件 / 写文件 / 精确替换 / 列目录 / 搜索 / 执行命令 / git / todo / 结束），全部**在本地执行**。
- **任务规划**：`todo` 工具让模型在多步任务前先列计划、完成后更新，进度可追踪。
- **人工审批**：`--approve` 开启后，执行命令等危险操作前询问用户确认（human-in-the-loop）。
- **项目级规则**：自动读取工作目录下的 `AGENTS.md` / `CLAUDE.md`，注入系统提示词定制 agent 行为。
- **上下文管理**：自研 token 估算 + 超预算时的「摘要式压缩」，压缩后消息结构仍合法（不拆散 tool_calls 与结果）。
- **多重终止条件**：无工具调用即结束、`finish` 工具、最大迭代上限、重复调用死循环检测。
- **健壮的错误处理**：工具异常反馈给模型自纠正；参数 JSON 非法时回传错误而非崩溃；命令超时控制；API 请求带指数退避重试。
- **沙箱安全**：文件与命令都限制在工作目录内，拒绝 `..` 路径越界。
- **离线可测**：核心逻辑与模型客户端解耦，单元测试用 FakeLLM 即可跑通，不消耗 API 额度。

## 快速开始

```bash
# 1. 安装依赖（Python >= 3.9）
pip install -r requirements.txt

# 2. 配置密钥（二选一）
cp .env.example .env   # 然后编辑 .env，填入 DEEPSEEK_API_KEY
# 或：export DEEPSEEK_API_KEY=sk-xxxx

# 3. 单次任务
python -m coding_agent "在工作目录里写一个 Python 脚本，读取 data.txt 里的数字并计算平均值和中位数"

# 4. 交互模式（省略任务参数；多轮会话，支持 /save /resume /sessions /clear）
python -m coding_agent

# 5. 运行测试（可选）
pip install pytest
python -m pytest
```

## 使用示例

```bash
# 打印详细过程（每一步工具调用及其结果、错误）
python -m coding_agent "把 README 里所有 'colour' 改成 'color'" --workspace ./examples/demo --verbose

# 指定工作目录与迭代上限
python -m coding_agent "重构 utils.py 并跑通测试" --workspace ./my_project --max-iterations 40

# 执行危险操作（命令）前人工确认
python -m coding_agent "重构 utils.py" --approve
```

> 想定制 agent 行为？在工作目录下放一个 `AGENTS.md`（或 `CLAUDE.md`），内容会被自动注入系统提示词，作为最高优先级的项目规则。

## 配置项

全部通过环境变量（或 `.env` 文件）注入：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | — | **必填**，DeepSeek API 密钥 |
| `LLM_BASE_URL` | `https://api.deepseek.com` | 接口地址 |
| `LLM_MODEL` | `deepseek-chat` | 模型名 |
| `LLM_TEMPERATURE` | `0.0` | 采样温度（编码任务用低温度更稳定） |
| `LLM_MAX_TOKENS` | `4096` | 单次回复最大 token |
| `AGENT_WORKSPACE` | `./workspace` | 工作目录（沙箱） |
| `AGENT_MAX_ITERATIONS` | `30` | 最大迭代轮数 |
| `AGENT_MAX_CONTEXT_TOKENS` | `60000` | 上下文预算（DeepSeek 128K 内留余量） |
| `AGENT_COMMAND_TIMEOUT` | `60` | 命令超时（秒） |

## 架构与设计决策

项目分层清晰、各模块职责单一：

```
用户任务
   │
   ▼
cli.py ──▶ Agent（核心循环）
              │ 1. 调用模型（llm.py）
              │ 2. 解析输出（parsing.py）
              │ 3. 执行工具（tools/）
              │ 4. 维护上下文（context.py + tokens.py）
              ▼
         最终回答
```

**关键设计决策（也是答辩可展开的点）：**

1. **为什么用 OpenAI 兼容接口？** DeepSeek 原生提供 OpenAI 兼容的 `/chat/completions`，用官方 `openai` 库作客户端即可，同时保留了以后换厂商的扩展空间（换 `base_url`/`model` 即可）。
2. **为什么用 `deepseek-chat` 而非 `deepseek-reasoner`？** 后者不支持（或不可靠支持）工具调用，而工具调用是 agent 的核心；`deepseek-chat`（V3.2）支持 function calling 且上下文 128K。
3. **为什么「工具定义在本地、执行在本地」？** 题目要求不得依赖服务端托管工具。工具的 JSON Schema 与本地执行函数都在仓库里，agent 只是把「要调哪个工具、参数是什么」告诉模型。
4. **为什么把「模型输出解析」独立成 `parsing.py`？** 模型返回的 `tool_calls.arguments` 是字符串，必须自己 `json.loads` 并校验类型；非法 JSON 不能崩溃，而要反馈给模型让它重试。
5. **为什么上下文压缩要「保证消息结构合法」？** OpenAI 协议要求每条 `tool` 结果之前都有对应的 `assistant.tool_calls`。压缩时若从中间切断会留下「孤儿 tool 消息」导致 400 错误，所以压缩点必须选在 user / assistant 消息边界。
6. **为什么用「模型自纠错」做错误处理？** 工具执行失败（文件不存在、替换不唯一、命令超时……）不直接终止，而是把错误文本作为 `tool` 结果回填，让模型读到报错后自行调整——这正是 agent 和普通脚本的本质区别。

## 工具清单

| 工具 | 作用 | 关键实现 |
| --- | --- | --- |
| `list_directory` | 列目录（可递归） | `os.walk`，跳过 .git 等 |
| `read_file` | 读文件（带行号，支持行区间） | 行号便于后续 edit |
| `write_file` | 创建/覆盖文件 | 自动建父目录 |
| `edit_file` | 精确字符串替换 | 唯一性校验，防误替换 |
| `search_content` | 正则搜索 | Python `re`，跨平台 |
| `run_command` | 执行命令 | `subprocess` + 超时 + 截断 |
| `git` | 只读查看 git 状态/差异/日志 | `git --no-pager`，仅 status/diff/log |
| `todo` | 维护任务清单 | 内存列表，整体覆盖 |
| `finish` | 结束并汇报 | 显式终止信号 |

所有文件/命令都经过路径沙箱校验，限制在工作目录内。

## 循环终止条件

1. 模型返回**不含 tool_calls** 的最终回答（`finished`）
2. 模型调用 `finish` 工具（`finish_tool`）
3. 达到 `AGENT_MAX_ITERATIONS` 上限（`max_iterations`）
4. 交互模式用户 `Ctrl+C` 中断
5. 附加保护：连续多轮发出**完全相同的工具调用**时，注入「换思路」提示，避免死循环

## 测试

```bash
python -m pytest
```

30 个用例覆盖：agent 循环的各终止路径、工具读写/替换/越界/超时、token 估算、上下文压缩的结构合法性、模型输出解析。测试使用 `tests/fakes.py` 的 `FakeLLM` 模拟模型，**完全离线、确定、可重复**。

## 安全说明

- `run_command` 使用 `shell=True`，意味着模型可执行任意命令，这是 coding agent 的固有特性。本项目通过工作目录沙箱限制影响范围；生产环境建议配合容器（如 Docker）或虚拟机隔离。
- API 密钥只通过环境变量 / `.env`（已 gitignore）提供，绝不出现在代码、提交历史或文档中。

## 项目结构

```
coding-agent-project/
├── coding_agent/
│   ├── agent.py            # 核心循环、终止条件、重复检测
│   ├── cli.py              # 命令行 + 交互 REPL
│   ├── config.py           # 环境变量配置
│   ├── context.py          # 对话历史 + 上下文压缩
│   ├── llm.py              # DeepSeek 客户端封装 + 摘要
│   ├── parsing.py          # 模型输出（tool_calls）解析
│   ├── tokens.py           # token 估算
│   ├── system_prompt.py    # 系统提示词
│   ├── errors.py           # 异常类型
│   └── tools/
│       ├── base.py         # 工具框架（定义/注册/分发）
│       ├── file_tools.py   # 文件读写与替换
│       ├── command_tool.py # 命令执行
│       └── search_tool.py  # 内容搜索
├── tests/                  # 离线单元测试
├── examples/               # 演示任务
├── README.txt              # 提交用说明（<=1000 字）
└── .env.example            # 环境变量模板
```
