"""LLMClient.chat_stream 的流式累积逻辑测试（离线，不依赖真实 API）。

重点覆盖流式协议里最容易出错的部分：tool_calls 按 index 分片下发，id/name
只在首片出现、arguments 是逐片拼接的增量字符串；usage 在最后一个 chunk。
"""

from coding_agent.config import Config
from coding_agent.llm import LLMClient


# ---- 构造假的 OpenAI 流式响应对象（结构与真实 SDK 解码结果一致）----


class _Fn:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _ToolCallDelta:
    def __init__(self, index, id=None, name=None, arguments=None):
        self.index = index
        self.id = id
        self.function = _Fn(name, arguments)


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _Choice:
    def __init__(self, delta, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason


class _Usage:
    def __init__(self, prompt_tokens, completion_tokens, total_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _Chunk:
    def __init__(self, delta, finish_reason=None, usage=None):
        self.choices = [_Choice(delta, finish_reason)]
        self.usage = usage


class _Completions:
    def __init__(self, stream):
        self._stream = stream

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self._stream


class _Chat:
    def __init__(self, stream):
        self.completions = _Completions(stream)


class _FakeOpenAI:
    def __init__(self, stream):
        self.chat = _Chat(stream)


def _client(stream) -> LLMClient:
    cfg = Config(api_key="test")
    client = LLMClient(cfg)
    client.client = _FakeOpenAI(stream)  # 替换真实客户端，注入假流
    return client


def test_stream_enables_stream_and_include_usage():
    chunks = [_Chunk(_Delta(content="ok"), finish_reason="stop", usage=_Usage(1, 2, 3))]
    client = _client(chunks)
    client.chat_stream([{"role": "user", "content": "q"}])
    kwargs = client.client.chat.completions.kwargs
    assert kwargs["stream"] is True
    # 开启 usage 回传，保证 token 统计与上下文压缩预算不因流式而丢
    assert kwargs["stream_options"] == {"include_usage": True}


def test_text_chunks_concatenated_and_forwarded():
    """文本增量逐片拼接成完整 content，并每片即时回调 on_text。"""
    chunks = [
        _Chunk(_Delta(content="你好，")),
        _Chunk(_Delta(content="答案是 42"), finish_reason="stop", usage=_Usage(10, 5, 15)),
    ]
    client = _client(chunks)
    seen = []
    resp = client.chat_stream([{"role": "user", "content": "q"}], on_text=seen.append)

    assert resp.content == "你好，答案是 42"
    assert resp.finish_reason == "stop"
    assert resp.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert seen == ["你好，", "答案是 42"]  # 每片增量各自回调
    assert resp.tool_calls == []


def test_tool_call_arguments_accumulated_across_chunks():
    """id/name 只在首片，arguments 跨 chunk 分片拼接，流结束后解析成 dict。"""
    chunks = [
        _Chunk(_Delta(tool_calls=[
            _ToolCallDelta(index=0, id="c0", name="write_file", arguments='{"path": "a'),
        ])),
        _Chunk(_Delta(tool_calls=[
            _ToolCallDelta(index=0, arguments='.txt", "content": "hi"}'),
        ])),
        _Chunk(_Delta(), finish_reason="tool_calls"),
    ]
    client = _client(chunks)
    resp = client.chat_stream([{"role": "user", "content": "写文件"}])

    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.id == "c0"
    assert tc.name == "write_file"
    assert tc.arguments == {"path": "a.txt", "content": "hi"}
    assert tc.parse_error is None


def test_multiple_tool_calls_grouped_by_index():
    """多个工具调用按 index 区分并各自累积，最终按 index 升序返回。"""
    chunks = [
        _Chunk(_Delta(tool_calls=[
            _ToolCallDelta(index=0, id="c0", name="list_directory", arguments="{}"),
            _ToolCallDelta(index=1, id="c1", name="read_file", arguments='{"path": "a'),
        ])),
        _Chunk(_Delta(tool_calls=[
            _ToolCallDelta(index=1, arguments='.txt"}'),
        ])),
    ]
    client = _client(chunks)
    resp = client.chat_stream([{"role": "user", "content": "任务"}])

    assert [tc.id for tc in resp.tool_calls] == ["c0", "c1"]
    assert resp.tool_calls[0].name == "list_directory"
    assert resp.tool_calls[1].arguments == {"path": "a.txt"}
