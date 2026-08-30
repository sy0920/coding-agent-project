"""测试用的 FakeLLM：按预设顺序返回响应，无需真实 API。

这样测试完全离线、确定、可重复，也印证了「agent 循环与模型客户端解耦」的设计。
"""

from coding_agent.llm import LLMResponse


class FakeLLM:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []  # 每次 chat 的 (messages, tools)
        self.summarize_calls = []

    def chat(self, messages, tools=None, max_retries=3):
        # 记录本次调用时的消息快照（拷贝而非引用），避免之后被 agent 追加消息而污染断言。
        self.calls.append((list(messages), tools))
        if not self.responses:
            return LLMResponse(content="done", tool_calls=[], finish_reason="stop", usage={})
        return self.responses.pop(0)

    def summarize(self, text, max_tokens=512):
        self.summarize_calls.append(text)
        return "（摘要）"
