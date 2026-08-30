"""命令行入口：单次任务模式 + 交互式 REPL。"""

import argparse
import os
import sys

# Windows 下终端编码可能是 GBK，强制用 UTF-8 输出并容错，保证中文正常显示
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

from .agent import Agent
from .config import Config
from .errors import AgentError
from .llm import LLMClient
from .system_prompt import build_system_prompt
from .tools import build_registry


def _make_step_printer():
    """构造进度回调：打印每一步工具调用。"""

    def step(name, arguments):
        if name == "finish":
            print(f"\n  ✓ 任务完成：{arguments.get('summary', '')}")
        else:
            brief = str(arguments)
            if len(brief) > 120:
                brief = brief[:120] + "…"
            print(f"\n  ▶ 调用工具 {name} {brief}")

    return step


def _run_task(config, agent, task, verbose):
    print(f"模型：{config.model}   工作目录：{os.path.abspath(config.workspace)}\n")
    print(f"任务：{task}\n")
    print("─" * 60)
    result = agent.run(task)
    print("\n" + "─" * 60)
    print("\n【结果】")
    print(result.final_answer or "（无输出）")
    if verbose:
        print(f"\n[迭代 {result.iterations} 轮 / 终止原因 {result.stop_reason} / "
              f"tokens {result.usage.get('total_tokens', 0)}]")
    return 0 if result.success else 1


def _repl(config, agent, verbose):
    print(f"coding-agent 交互模式（模型 {config.model}）")
    print("输入编程任务开始；后续输入会延续同一会话（agent 记住上下文）。")
    print("输入 exit / quit / 空行退出；输入 clear 清空会话重新开始。\n")
    conversation = None
    while True:
        try:
            task = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if task in ("", "exit", "quit"):
            break
        if task in ("clear", "/clear"):
            conversation = None
            print("（已清空会话，开始新会话）\n")
            continue
        result = agent.run(task, conversation)
        conversation = result.conversation
        print("\n" + "─" * 60)
        print(result.final_answer or "（无输出）")
        if verbose:
            print(f"[迭代 {result.iterations} 轮 / 终止原因 {result.stop_reason}]")
        print()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="coding-agent",
        description="一个基于 DeepSeek 的自主编程智能体（coding agent）。",
    )
    parser.add_argument("task", nargs="?", help="编程任务描述（省略则进入交互模式）")
    parser.add_argument("--workspace", help="工作目录（agent 在其中读写与执行命令）")
    parser.add_argument("--max-iterations", type=int, help="最大迭代轮数")
    parser.add_argument("--verbose", action="store_true", help="打印每一步工具调用与统计信息")
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.workspace:
        config.workspace = args.workspace
    if args.max_iterations:
        config.max_iterations = args.max_iterations

    try:
        os.makedirs(config.workspace, exist_ok=True)
        llm = LLMClient(config)
        tools = build_registry(config)
        agent = Agent(
            llm,
            tools,
            config,
            build_system_prompt(config.workspace),
            on_step=_make_step_printer() if args.verbose else None,
        )
    except AgentError as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        return 2

    if args.task:
        return _run_task(config, agent, args.task, args.verbose)
    return _repl(config, agent, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
