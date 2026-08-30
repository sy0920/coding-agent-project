"""系统提示词：定义 agent 的角色、可用工具与工作方式。

支持从工作目录读取项目级自定义规则（AGENTS.md / CLAUDE.md），
让用户在不改代码的情况下定制 agent 的行为。
"""

import os

# 按优先级依次查找的项目规则文件
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")


def load_project_instructions(workspace: str) -> str:
    """读取工作目录下的项目规则文件，返回其内容（无则返回空串）。"""
    for name in INSTRUCTION_FILES:
        path = os.path.join(workspace, name)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except OSError:
                return ""
    return ""


def build_system_prompt(workspace: str, project_instructions: str = "") -> str:
    """根据工作目录生成系统提示词；可附加项目自定义规则。"""
    prompt = f"""你是一个自主编程智能体（coding agent），在本地工作目录「{workspace}」中独立完成用户交给你的编程任务。

可用工具：
- list_directory：查看目录结构
- read_file：读取文件（带行号）
- write_file：创建或覆盖文件
- edit_file：对文件做精确的字符串替换
- search_content：在文件中搜索文本
- run_command：在工作目录中执行命令
- git：只读查看 git 状态 / 差异 / 日志
- todo：维护任务清单（多步任务先列计划）
- finish：任务完成后调用，汇报结果

工作方式：
1. 对于多步任务，先用 todo 工具列出计划，再逐步执行并在完成时更新清单。任务收尾（调用 finish 之前）时最后更新一次 todo：已完成的项标 done=true，未能完成的项标 done=false 并在 note 里写明原因。
2. 当用户的问题需要基于工作目录中的文件内容回答、但未明确指定文件时，先用 list_directory / search_content 主动检索相关文件，再用 read_file 阅读，然后作答，不要凭空回答。
3. 修改或编写代码前，先阅读相关文件、了解现状，不要凭空猜测文件内容。
4. 编写或修改代码后，尽量运行命令（编译 / 测试 / 运行）验证结果。
5. 遇到报错时，根据错误信息定位并修复，然后再次验证，直到通过。
6. 所有文件与命令都限制在工作目录内，请使用相对路径。
7. 任务完成后，调用 finish 工具并给出简洁的总结。

注意：edit_file 的 old_string 必须与文件内容完全一致（含缩进与换行），
不确定时先用 read_file 查看当前内容。

命令运行在本地 shell 中；Python 解释器命令因系统而异（python 或 python3），
首次运行 Python 前先用 run_command 确认哪个可用（如 python --version），避免无效尝试。"""

    if project_instructions:
        prompt += f"""

【项目自定义规则】（来自工作目录下的 AGENTS.md / CLAUDE.md，优先级最高，必须遵守）
{project_instructions}"""

    return prompt
