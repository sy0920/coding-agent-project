"""agent 核心循环（本项目的心脏）。

一个完整的「思考—行动—观察」循环：

    while 未结束:
        1. （可选）压缩上下文
        2. 调用模型，得到回复
        3. 若模型没有工具调用 → 视为最终回答，结束
        4. 否则逐个在本地执行工具，把结果回填进历史
        5. 检测重复/死循环，必要时给模型注入提示

循环终止条件（显式枚举，便于讲解与测试）：
  1. 模型返回不含 tool_calls 的最终回答（stop_reason="finished"）；
  2. 模型调用 finish 工具（stop_reason="finish_tool"）；
  3. 达到最大迭代次数（stop_reason="max_iterations"）；
  4. 交互模式下用户 Ctrl+C 中断（由 CLI 层处理）。
另设「重复检测」：连续多轮发出完全相同的工具调用时，注入换思路提示，
避免模型陷入死循环。
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from .context import Conversation


@dataclass
class AgentResult:
    """一次任务运行的最终结果。"""

    success: bool
    final_answer: str = ""
    iterations: int = 0
    stop_reason: str = ""  # finished / finish_tool / max_iterations
    usage: dict = field(default_factory=dict)
    # 本轮结束时的话历史；交互模式下可把它传回下一次 run() 以延续多轮会话。
    conversation: Optional[Conversation] = None

    def __str__(self) -> str:
        return self.final_answer


class Agent:
    def __init__(
        self,
        llm,
        tools,
        config,
        system_prompt: str,
        on_step: Optional[Callable[[str, dict, str], None]] = None,
        approver: Optional[Callable[[str, dict], bool]] = None,
        on_text: Optional[Callable[[str], None]] = None,
        approve_all: bool = False,
    ):
        self.llm = llm
        self.tools = tools
        self.config = config
        self.system_prompt = system_prompt
        # 进度回调 on_step(name, arguments, result)，供 CLI 打印过程；
        # name 通常是工具名，也可能是 "compact"（上下文压缩）这类循环内事件。
        self.on_step = on_step or (lambda name, args, result: None)
        # 审批回调 approver(name, arguments) -> bool；为 None 表示完全不做人工审批。
        self.approver = approver
        # 审批范围：True = 对 modify 与 dangerous 都审批；False = 只审批 dangerous。
        self.approve_all = approve_all
        # 流式文本回调 on_text(text)；为 None 时走非流式 chat，否则走 chat_stream
        self.on_text = on_text

    def run(self, task: str, conversation: Optional[Conversation] = None) -> AgentResult:
        # 传入已有会话则复用（多轮对话延续），否则新建一个全新会话。
        ctx = conversation or Conversation(self.system_prompt, self.config.max_context_tokens)
        ctx.add_user(task)

        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        last_signature = None
        repeat_count = 0

        for i in range(self.config.max_iterations):
            # 1. 上下文预算控制（超预算时压缩，并通过 on_step 通知外部以便观测）
            before = ctx.total_tokens
            if ctx.maybe_compact(self.llm.summarize):
                self.on_step(
                    "compact",
                    {"before": before, "after": ctx.total_tokens},
                    "较早的历史已压缩为摘要",
                )

            # 2. 调用模型（配置了 on_text 时走流式，实时打印文本增量）
            if self.on_text is not None:
                resp = self.llm.chat_stream(
                    ctx.messages, self.tools.to_openai_tools(), on_text=self.on_text
                )
            else:
                resp = self.llm.chat(ctx.messages, self.tools.to_openai_tools())
            self._accumulate_usage(total_usage, resp.usage)

            # 3. 无工具调用 → 最终回答
            if not resp.tool_calls:
                ctx.add_assistant(resp.content, [])
                return AgentResult(True, resp.content or "", i + 1, "finished", total_usage, ctx)

            # 4. 有工具调用 → 记录 assistant 消息，逐个执行
            ctx.add_assistant(resp.content, resp.tool_calls)

            finish_summary = None
            for tc in resp.tool_calls:
                if tc.name == "finish":
                    finish_summary = tc.arguments.get("summary", "")
                    ctx.add_tool_result(tc.id, tc.name, "任务已结束")
                    self.on_step("finish", {"summary": finish_summary}, "任务已结束")
                    continue
                # 审批策略：readonly 永不审批；modify 仅在 approve_all 下审批；
                # dangerous 默认就审批。审批回调为 None（未配置）则一律直接执行。
                risk = self.tools.risk_of(tc.name)
                needs_approval = risk == "dangerous" or (
                    self.approve_all and risk == "modify"
                )
                if (
                    needs_approval
                    and self.approver is not None
                    and not self.approver(tc.name, tc.arguments)
                ):
                    result = "用户拒绝了该操作，未执行。"
                else:
                    result = self._execute(tc)
                ctx.add_tool_result(tc.id, tc.name, result)
                self.on_step(tc.name, tc.arguments, result)

            if finish_summary is not None:
                return AgentResult(True, finish_summary, i + 1, "finish_tool", total_usage, ctx)

            # 5. 重复 / 死循环检测
            signature = self._signature(resp.tool_calls)
            if signature == last_signature:
                repeat_count += 1
                if repeat_count >= 3:
                    ctx.add_user(
                        "你似乎陷入了重复循环：连续多轮发出了完全相同的工具调用。"
                        "请检查工具返回结果，换一种思路，或调用 finish 汇报当前进展。"
                    )
                    repeat_count = 0
            else:
                last_signature = signature
                repeat_count = 1

        return AgentResult(
            False,
            f"达到最大迭代次数（{self.config.max_iterations}）仍未完成任务。",
            self.config.max_iterations,
            "max_iterations",
            total_usage,
            ctx,
        )

    # ---- 内部 ---------------------------------------------------------

    def _execute(self, tc) -> str:
        """执行单个工具调用；参数解析失败时把错误反馈给模型。"""
        if tc.parse_error:
            return f"错误：工具「{tc.name}」的调用参数无法解析：{tc.parse_error}"
        return self.tools.execute(tc.name, tc.arguments)

    @staticmethod
    def _signature(tool_calls) -> tuple:
        """本轮工具调用的「指纹」，用于重复检测（对参数顺序不敏感）。"""
        return tuple((tc.name, tuple(sorted(tc.arguments.items()))) for tc in tool_calls)

    @staticmethod
    def _accumulate_usage(total: dict, usage: dict) -> None:
        for key in total:
            total[key] += usage.get(key, 0)
