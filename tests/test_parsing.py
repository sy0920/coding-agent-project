from coding_agent.parsing import ToolCall, parse_tool_calls


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
