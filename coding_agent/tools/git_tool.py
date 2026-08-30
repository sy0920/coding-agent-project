"""Git 工具：只读地查看仓库状态、工作区差异与提交日志。

只提供只读命令（status / diff / log），不提供 commit / push 等写操作，
避免 agent 意外改动仓库历史；确需提交时可用 run_command 显式执行。
"""

import subprocess

from .base import truncate


class GitTool:
    def __init__(self, workspace: str, timeout: int = 30):
        self.workspace = workspace
        self.timeout = timeout

    # 允许的只读子命令 -> 实际 git 参数
    _SUBCOMMANDS = {
        "status": ["status", "--short", "--branch"],
        "diff": ["diff"],
        "log": ["log", "--oneline", "-n", "20"],
    }

    def git(self, subcommand: str) -> str:
        if subcommand not in self._SUBCOMMANDS:
            return (
                f"错误：不支持的 git 子命令 {subcommand!r}，"
                f"可用：{', '.join(self._SUBCOMMANDS)}"
            )
        return self._run(*self._SUBCOMMANDS[subcommand])

    def _run(self, *args: str) -> str:
        try:
            proc = subprocess.run(
                ["git", "--no-pager", *args],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.timeout,
            )
        except FileNotFoundError:
            return "错误：未找到 git 命令"
        except subprocess.TimeoutExpired:
            return "错误：git 命令执行超时"
        except Exception as exc:  # noqa: BLE001
            return f"错误：git 执行失败：{exc}"

        out = proc.stdout or ""
        if proc.stderr:
            out = (out + ("\n" if out else "") + "[stderr]\n" + proc.stderr).rstrip("\n")
        return truncate(out) if out.strip() else "(无输出)"
