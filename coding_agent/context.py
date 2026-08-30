"""对话历史与上下文管理。

维护 OpenAI 兼容格式的消息列表，负责：
- 消息的增删（user / assistant / tool 三种角色）；
- 基于 token 估算的上下文预算控制；
- 超预算时对历史做「摘要式压缩」，同时保证压缩后消息结构仍然合法
  （绝不把 assistant 的 tool_calls 与其对应的 tool 结果拆散）。
"""

from .tokens import estimate_messages_tokens


class Conversation:
    """一段 agent 会话的消息历史。"""

    def __init__(self, system_prompt: str, max_context_tokens: int):
        self.system_prompt = system_prompt
        self.max_context_tokens = max_context_tokens
        self.messages = [{"role": "system", "content": system_prompt}]

    # ---- 消息增删 -----------------------------------------------------

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, content, tool_calls) -> None:
        """记录 assistant 消息；tool_calls 为自定义 ToolCall 列表（可为空）。"""
        msg = {"role": "assistant", "content": content or None}
        if tool_calls:
            msg["tool_calls"] = [tc.to_api_dict() for tc in tool_calls]
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        """记录一次工具调用的返回结果（role=tool，需携带对应的 id）。"""
        self.messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": content}
        )

    # ---- 上下文预算 ---------------------------------------------------

    @property
    def total_tokens(self) -> int:
        return estimate_messages_tokens(self.messages)

    def maybe_compact(self, summarize_fn) -> bool:
        """若估算 token 数超过预算，则压缩历史；返回是否发生了压缩。

        summarize_fn(text) -> str：由外部传入的摘要函数（通常是 LLM 调用），
        这样上下文管理不直接依赖模型客户端，职责解耦、便于测试。
        """
        if self.total_tokens <= self.max_context_tokens:
            return False
        self._compact(summarize_fn)
        return True

    def _compact(self, summarize_fn) -> None:
        """把较早的历史压缩成一条摘要消息，只保留最近的一整段「安全」上下文。

        关键点：保留段的起点必须是 user 或 assistant 消息。这样位于保留段内的
        每条 tool 结果消息，其对应的 assistant tool_calls 也一定在保留段内，
        不会出现「孤儿 tool 消息」，从而保证后续请求不报 400 错误。
        """
        if len(self.messages) <= 3:
            return

        tail_budget = max(self.max_context_tokens // 2, 2000)
        cut = 1  # 默认只保留 system 之后从 user 开始
        running = 0
        for i in range(len(self.messages) - 1, 0, -1):
            m = self.messages[i]
            running += estimate_messages_tokens([m])
            if m["role"] in ("user", "assistant"):
                cut = i  # 记录最近的安全切割点
            if running >= tail_budget:
                break

        middle = self.messages[1:cut]
        if not middle:
            return

        summary = summarize_fn(self._to_text(middle))
        summary_msg = {
            "role": "system",
            "content": "[历史摘要]\n" + (summary or ""),
        }
        self.messages = [self.messages[0], summary_msg] + self.messages[cut:]

    # ---- 序列化（会话持久化） -----------------------------------------

    def to_dict(self) -> dict:
        """序列化为可 JSON 存储的字典（messages 本就是 OpenAI 格式 dict 列表）。"""
        return {"messages": self.messages}

    @classmethod
    def from_dict(cls, data: dict, max_context_tokens: int) -> "Conversation":
        """从序列化结果恢复会话。system 提示词从首条消息里取回。"""
        messages = data["messages"]
        system_prompt = ""
        if messages and messages[0].get("role") == "system":
            system_prompt = messages[0].get("content") or ""
        conv = cls(system_prompt, max_context_tokens)
        conv.messages = messages
        return conv

    # ---- 辅助 ---------------------------------------------------------

    @staticmethod
    def _to_text(messages) -> str:
        """把一段消息转成可供摘要的纯文本。"""
        lines = []
        for m in messages:
            role = m["role"]
            content = m.get("content") or ""
            if role == "tool":
                lines.append(f"[工具返回] {content}")
                continue
            if content:
                lines.append(f"[{role}] {content}")
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function", {})
                lines.append(
                    f"[{role} 调用工具] {fn.get('name')}({fn.get('arguments', '')})"
                )
        return "\n".join(lines)
