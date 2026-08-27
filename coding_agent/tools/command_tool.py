"""命令工具：在工作目录中执行 shell 命令。

实现要点：
- 使用 subprocess 在本地执行（题目要求「不得依赖 API 服务端托管的代码执行」）；
- cwd 固定为工作目录，命令在该沙箱内运行；
- 设置超时，超时/异常均反馈给模型而不是让 agent 挂起；
- 合并 stdout/stderr 并附带退出码、截断超长输出。

注意：shell=True 意味着模型可执行任意命令，这是 coding agent 的固有特性；
生产环境应配合容器沙箱使用（见 README 的「安全说明」）。
"""

import subprocess

from .base import truncate


class CommandTool:
    def __init__(self, workspace: str, timeout: int = 60):
        self.workspace = workspace
        self.timeout = timeout

    def run_command(self, command: str) -> str:
        if not command or not command.strip():
            return "错误：命令为空"
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                errors="replace",  # 输出含无法解码的字节时不崩溃，替换为占位符
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（>{self.timeout}s）：{command}"
        except Exception as exc:  # noqa: BLE001
            return f"错误：命令执行失败：{exc}"

        out = proc.stdout or ""
        if proc.stderr:
            out = (out + ("\n" if out else "") + "[stderr]\n" + proc.stderr).rstrip("\n")
        status = f"退出码 {proc.returncode}"
        return f"{status}\n{truncate(out)}" if out.strip() else status
