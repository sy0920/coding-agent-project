from coding_agent.context import Conversation
from coding_agent.parsing import ToolCall


def test_add_messages_and_token_count():
    c = Conversation("sys", 100000)
    c.add_user("hello")
    c.add_assistant("hi", [])
    assert c.total_tokens > 0
    assert c.messages[0]["role"] == "system"


def test_assistant_with_tool_calls_serialized():
    c = Conversation("sys", 100000)
    c.add_assistant(None, [ToolCall("c1", "write_file", {"path": "a", "content": "x"})])
    assert c.messages[-1]["tool_calls"][0]["id"] == "c1"
    assert c.messages[-1]["tool_calls"][0]["function"]["name"] == "write_file"


def test_compaction_preserves_tool_result_pairing():
    c = Conversation("sys", 100000)
    c.add_user("task")
    for i in range(20):
        c.add_assistant(None, [ToolCall(f"c{i}", "list_directory", {})])
        c.add_tool_result(f"c{i}", "list_directory", "x" * 500)
    c.add_assistant("done", [])

    # 把预算设得很小，强制触发压缩
    c.max_context_tokens = 100
    changed = c.maybe_compact(lambda text: "摘要")
    assert changed

    # 压缩后：第一条仍是 system；且不允许出现「孤儿 tool 消息」——
    # 每条 tool 结果之前都必须在保留段内找到对应的 assistant tool_calls。
    assert c.messages[0]["role"] == "system"
    for i, m in enumerate(c.messages):
        if m["role"] != "tool":
            continue
        tid = m["tool_call_id"]
        found = False
        for j in range(i - 1, -1, -1):
            prev = c.messages[j]
            if prev["role"] == "assistant" and prev.get("tool_calls"):
                ids = [t["id"] for t in prev["tool_calls"]]
                if tid in ids:
                    found = True
                    break
        assert found, f"出现孤儿 tool 消息 {tid}"


def test_compaction_calls_summarize_once():
    c = Conversation("sys", 100000)
    c.add_user("task")
    for i in range(30):
        c.add_assistant(None, [ToolCall(f"c{i}", "list_directory", {})])
        c.add_tool_result(f"c{i}", "list_directory", "y" * 300)
    c.max_context_tokens = 100
    calls = []
    c.maybe_compact(lambda text: calls.append(text) or "摘要")
    assert len(calls) == 1
    # 摘要消息应作为第二条 system 消息存在
    assert c.messages[1]["role"] == "system"
    assert "历史摘要" in c.messages[1]["content"]
