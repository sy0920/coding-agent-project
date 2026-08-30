# 演示剧本（demo script）

一份覆盖全部核心功能的演示流程，供**录制视频**与**答辩复现**使用。所有命令都在项目根目录 `coding-agent-project/` 下执行，工作区为 `./workspace`。

## 功能覆盖清单

| 功能 | 演示点 |
| --- | --- |
| 任务规划（todo） | 每轮开头先列计划 |
| 多文件协作 | wordcount.py / main.py / README.md / sample.txt |
| 第一次生成 → 第二次修改+新增 | 演示 A 的第 1、2 轮 |
| 同一会话多次对话 | 演示 A 连续两轮不退出，第二轮直接读第一轮生成的文件 |
| 读取文件（不打印正文） | `read_file` 只显「共 N 行」摘要 |
| 处理错误（自纠正） | 命令报错 → 模型读 stderr → 换写法重试 |
| edit_file 红绿 diff | 加 `filter_stopwords` 时显示 `- 旧 / + 新` |
| 会话持久化 / 切换 | `/save` `/resume` `/switch` `/sessions` `/clear` |
| 基于文件问答 + 主动检索 | 演示 C：不给路径，自己定位文件 |
| 人工审批（human-in-the-loop） | 演示 D：拒绝 / 通过 |
| 上下文压缩 | 见「附：展示上下文压缩」 |

---

## 准备

先清空工作区（下面这条用 Python 一行，在 PowerShell / bash 下都能跑，避免 `rm -rf` 在 PowerShell 被当成 `Remove-Item` 参数而报错）：

```bash
python -c "import shutil,os; shutil.rmtree('workspace', ignore_errors=True); os.makedirs('workspace', exist_ok=True)"
```

> 用 shell 原生命令也行：bash 是 `rm -rf workspace/*`，PowerShell 是 `Remove-Item workspace\* -Recurse -Force`。

然后进入交互模式：

```bash
python -m coding_agent --verbose
```

> 手动逐行输入中文任务时无需任何额外设置；只有用管道脚本喂入中文时才需在 bash 下加 `PYTHONUTF8=1` 前缀。

## 演示 A：多文件项目 + 多轮会话 + 错误自纠正

进入交互模式后，**连续**输入下面两轮（中间不要 `/clear`）：

### 第 1 轮（生成骨架）

```text
在工作目录创建一个名为 texttool 的 Python 项目，包含三个文件：wordcount.py 实现 count_words(text) 返回词频字典（忽略大小写、只统计字母数字单词）；main.py 作为命令行入口读取指定文件并打印频率最高的前10个词；README.md 简述用途。写完后试运行验证。
```

### 第 2 轮（在基础上修改 + 新增）

```text
继续完善这个项目：给 wordcount.py 增加 filter_stopwords(words, stopwords) 函数用于过滤停用词；修改 main.py 让它支持一次传入多个文件并合并统计；新建 sample.txt 写入一段英文文本作为测试数据；最后运行 python main.py sample.txt 验证结果。
```

**关键观察点：**

- 每轮开头 `todo` 列计划。
- 第 2 轮**开头直接 `read_file`** 第一轮生成的 `wordcount.py` / `main.py`（没有重新 `list_directory`，证明会话延续）。
- `edit_file` 的红绿 diff：

```text
▶ 修改 texttool/wordcount.py：
     -     return dict(Counter(word.lower() for word in words))
     +     return dict(Counter(word.lower() for word in words))
     + def filter_stopwords(words, stopwords): …
```

- 错误自纠正：模型在命令里塞 `; echo "exit=$?"` 被 argparse 报 `unrecognized arguments`，读 stderr 后改成分步执行。

## 演示 B：会话持久化 + 切换 + 文件问答

继续在交互模式输入：

```text
/save analyzer                 # 命名保存当前会话
/resume analyzer               # 恢复
sample.txt 里出现次数最多的词是什么？出现了几次？     # 文件问答（会话里记得路径）
/clear                         # 清空，隔离新会话
写一个 hello.py，打印 hello world                    # 全新会话、从零开始
/switch analyzer               # 切回保存的会话
更新 README.md，补充 filter_stopwords 函数和 --no-stopwords 选项的用法说明
/sessions                      # 列出所有会话
exit
```

**关键观察点：** `/resume` 后直接读 `texttool/sample.txt`（不重新探索）；`/clear` 后写 `hello.py` 是从零开始（不记得 texttool）；`/switch` 回来后又能直接改 `texttool/README.md`。

## 演示 C：主动检索（不给路径）

退出交互模式，用单次任务模式，**只给文件名、不给路径**：

```bash
python -m coding_agent "sample.txt 里出现次数最多的词是什么？出现了几次？" --workspace ./workspace --verbose
```

**关键观察点：** agent 先两级 `list_directory`（`{}` → `texttool`）定位到 `sample.txt`，再 `read_file` 分析。这正是「未指定文件时主动检索」的系统提示词在起作用。

## 演示 D：人工审批（--approve）

运行下面命令，出现 `⚠ 是否执行 run_command …？[y/N]` 时手动输入 `y`（通过）或 `n`（拒绝）：

```bash
python -m coding_agent "写一个快排程序" --workspace ./workspace --approve --verbose
```

- 输入 `y` → 命令执行成功，输出 `hello world`；
- 输入 `n` → 命令不执行，回填「用户拒绝了该操作」，模型据此调整（例如改从文件内容推断答案）。

> 想用管道脚本非交互喂入：bash 用 `printf 'y\n' | python …`，PowerShell 用 `"y" | python …`（换行用 PowerShell 的反引号 n）。

**关键观察点：** 每次 `run_command` 前都弹出 `⚠ 是否执行 run_command …？[y/N]`；输入 `y` 命令执行成功（输出 `hello world`），输入 `n` 命令不执行、回填「用户拒绝了该操作」，模型据此调整或改从文件内容推断答案。

---

## 附：上下文压缩（如何验证）

上下文压缩在估算 token 超过 `AGENT_MAX_CONTEXT_TOKENS` 时自动触发，触发时 `--verbose` 打印：

```text
⚠ 上下文压缩 2103 → 1450 tokens
```

实现见 `context.py` 的 `maybe_compact`：超预算后把较早历史摘要成一条 `[历史摘要]` 消息，只保留最近一段，并保证不拆散 assistant 的 tool_calls 与其对应的 tool 结果。

**为什么演示里看不到它**：压缩有两个硬条件——(1) 历史估算 token 超过预算；(2) 保留的「最近一段」至少 2000 token（`tail_budget = max(预算/2, 2000)`）。也就是说，只有历史足够长（超过 2000 token 且更早还有可摘要内容）才会真正压缩；默认预算 60000，正常短任务碰不到，视频里也演不出来。

它的正确性由单元测试保证：`tests/test_context.py` 构造 20+ 轮、每条 300~500 字符的历史强制触发，验证「压缩后无孤儿 tool 消息」「摘要消息作为第二条 system 存在」。答辩时可直接引用这两个测试 + 上面的日志格式说明机制。
