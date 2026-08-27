from coding_agent.tokens import estimate_messages_tokens, estimate_tokens


def test_estimate_ascii():
    # 5 个 ASCII 字符 → ceil(5/4) = 2
    assert estimate_tokens("hello") == 2


def test_estimate_cjk():
    # 4 个中文字符 → 4 token
    assert estimate_tokens("你好世界") == 4


def test_estimate_mixed():
    # 2 中文 + 2 ASCII → 2 + ceil(2/4) = 3
    assert estimate_tokens("你好ab") == 3


def test_estimate_empty():
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0


def test_messages_tokens_includes_tool_calls():
    msgs = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": None, "tool_calls": [{"function": {"arguments": "{}"}}]},
    ]
    # 用户消息 2 token；assistant 无 content，工具参数 "{}" 约 1 token
    assert estimate_messages_tokens(msgs) >= 2
