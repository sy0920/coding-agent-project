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
from .session import SessionStore
from .system_prompt import build_system_prompt, load_project_instructions
from .tools import build_registry


def _clip(text, limit: int = 120) -> str:
    """把文本压成单行并截断，用于简洁的过程展示。"""
    text = str(text) if text is not None else ""
    text = text.replace("\r", "").replace("\n", "\\n")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def _format_step(name: str, arguments: dict, result: str) -> str:
    """把一次工具调用格式化为简洁可读文本：不刷屏、突出「改了什么」。

    关键设计：工具返回的完整结果仍原样回填给模型（模型需要全文），
    这里只是给用户看的人类可读摘要，两者解耦。
    """
    is_error = (result or "").startswith("错误")

    if name == "read_file":
        # 只取结果首行摘要（共 N 行），不打印正文
        head = (result or "").split("\n", 1)[0]
        mark = "✗" if is_error else "↳"
        return f"▶ 读取 {arguments.get('path', '?')}\n     {mark} {head}"

    if name == "write_file":
        path = arguments.get("path", "?")
        if is_error:
            return f"▶ 写入 {path}\n     ✗ {result}"
        return f"▶ 写入 {path}（{len(arguments.get('content', ''))} 字符）"

    if name == "edit_file":
        path = arguments.get("path", "?")
        if is_error:
            return f"▶ 修改 {path}\n     ✗ {result}"
        old = _clip(arguments.get("old_string", ""))
        new = _clip(arguments.get("new_string", ""))
        return f"▶ 修改 {path}：\n     - {old}\n     + {new}"

    # 其余工具（run_command / search_content / list_directory / git / todo 等）
    brief = _clip(arguments)
    out = _clip(result, 300)
    mark = "✗" if is_error else "↳"
    return f"▶ {name} {brief}\n     {mark} {out}"


def _make_step_printer():
    """构造进度回调：打印每一步工具调用、结果与错误（人类可读摘要）。"""

    def step(name, arguments, result):
        if name == "finish":
            print(f"\n  ✓ 任务完成：{arguments.get('summary', '')}")
            return
        print("\n  " + _format_step(name, arguments, result))

    return step


def _make_approver():
    """构造危险操作审批回调：执行命令前询问用户（y 通过，其它拒绝）。"""

    def approve(name, arguments):
        brief = str(arguments)
        if len(brief) > 120:
            brief = brief[:120] + "…"
        while True:
            try:
                ans = input(f"  ⚠ 是否执行 {name} {brief}？[y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False
            if ans in ("y", "yes"):
                return True
            if ans in ("", "n", "no"):
                return False

    return approve


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


def _handle_session_command(task, conversation, current_name, store, max_context_tokens):
    """解析会话管理命令（以 / 开头，避免与自然语言任务混淆）。

    返回 (是否命中命令, 更新后的会话, 更新后的会话名, 提示语)。未命中时前三项原样返回。
    """
    cmd, _, arg = task.partition(" ")
    cmd = cmd.lower()
    arg = arg.strip()

    if cmd in ("/clear", "clear") and not arg:
        return True, None, "default", "（已清空会话，开始新会话）"

    if cmd == "/save":
        if not arg:
            return True, conversation, current_name, "用法：/save <名字>"
        if conversation is None:
            return True, conversation, current_name, "（当前没有会话，先输入一个任务再保存）"
        try:
            store.save(arg, conversation)
        except ValueError as exc:
            return True, conversation, current_name, f"（保存失败：{exc}）"
        return True, conversation, arg, f"（会话已保存为 {arg}）"

    if cmd == "/sessions":
        names = store.list_names()
        if not names:
            return True, conversation, current_name, "（暂无已保存会话）"
        return True, conversation, current_name, "已保存会话：" + "、".join(names)

    if cmd in ("/resume", "/switch"):
        if not arg:
            return True, conversation, current_name, f"用法：{cmd} <名字>"
        if not store.exists(arg):
            return True, conversation, current_name, f"（会话 {arg} 不存在，用 /sessions 查看）"
        try:
            conv = store.load(arg, max_context_tokens)
        except ValueError as exc:
            return True, conversation, current_name, f"（恢复失败：{exc}）"
        return True, conv, arg, f"（已恢复会话 {arg}）"

    return False, conversation, current_name, None


def _repl(config, agent, verbose):
    store = SessionStore(os.path.join(config.workspace, ".sessions"))
    print(f"coding-agent 交互模式（模型 {config.model}）")
    print("输入编程任务开始；后续输入会延续同一会话（agent 记住上下文，每轮自动保存）。")
    print("会话命令：/save <名字> 保存 · /resume <名字> 恢复 · /switch <名字> 切换 · "
          "/sessions 列出 · /clear 清空；输入 exit / quit / 空行退出。\n")
    conversation = None
    current_name = "default"
    while True:
        try:
            task = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if task in ("", "exit", "quit"):
            break

        handled, conversation, current_name, message = _handle_session_command(
            task, conversation, current_name, store, config.max_context_tokens
        )
        if handled:
            print(message)
            print()
            continue

        result = agent.run(task, conversation)
        conversation = result.conversation
        # 自动持久化：每轮结束自动落盘，退出后下次仍可 /resume 恢复
        store.save(current_name, conversation)
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
    parser.add_argument("--verbose", action="store_true", help="打印每一步工具调用、结果与统计信息")
    parser.add_argument("--approve", action="store_true",
                        help="执行危险操作（如命令）前询问用户确认")
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
        instructions = load_project_instructions(config.workspace)
        agent = Agent(
            llm,
            tools,
            config,
            build_system_prompt(config.workspace, instructions),
            on_step=_make_step_printer() if args.verbose else None,
            approver=_make_approver() if args.approve else None,
        )
    except AgentError as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        return 2

    if args.task:
        return _run_task(config, agent, args.task, args.verbose)
    return _repl(config, agent, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
