from coding_agent.parsing import ToolCall, parse_streamed_tool_calls, parse_tool_calls


class _FakeFn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeTC:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = _FakeFn(name, arguments)


def test_parse_valid():
    raw = [_FakeTC("c1", "write_file", '{"path": "a.txt", "content": "hi"}')]
    tcs = parse_tool_calls(raw)
    assert len(tcs) == 1
    assert tcs[0].name == "write_file"
    assert tcs[0].arguments == {"path": "a.txt", "content": "hi"}
    assert tcs[0].parse_error is None


def test_parse_invalid_json():
    raw = [_FakeTC("c1", "run_command", "not json")]
    tcs = parse_tool_calls(raw)
    assert tcs[0].parse_error is not None
    assert tcs[0].arguments == {}


def test_parse_empty_args():
    raw = [_FakeTC("c1", "list_directory", "")]
    tcs = parse_tool_calls(raw)
    assert tcs[0].arguments == {}
    assert tcs[0].parse_error is None


def test_to_api_dict_roundtrip():
    tc = ToolCall("c1", "finish", {"summary": "完成"})
    d = tc.to_api_dict()
    assert d["type"] == "function"
    assert d["function"]["name"] == "finish"
    assert d["id"] == "c1"


def test_parse_streamed_tool_calls_sorted_by_index():
    """流式累积的 slots 应按 index 升序解析成 ToolCall。"""
    slots = {
        1: {"id": "c1", "name": "read_file", "arguments": '{"path": "a.txt"}'},
        0: {"id": "c0", "name": "list_directory", "arguments": "{}"},
    }
    tcs = parse_streamed_tool_calls(slots)
    assert [tc.id for tc in tcs] == ["c0", "c1"]
    assert tcs[0].name == "list_directory" and tcs[0].arguments == {}
    assert tcs[1].name == "read_file" and tcs[1].arguments == {"path": "a.txt"}


def test_parse_streamed_tool_calls_invalid_json():
    """流式累积出的非法 arguments 同样记录 parse_error 而非抛异常。"""
    slots = {0: {"id": "c0", "name": "run_command", "arguments": "not json"}}
    tcs = parse_streamed_tool_calls(slots)
    assert tcs[0].parse_error is not None
    assert tcs[0].arguments == {}
