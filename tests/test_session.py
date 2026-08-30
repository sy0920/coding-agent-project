from coding_agent.context import Conversation
from coding_agent.parsing import ToolCall
from coding_agent.session import SessionStore


def _conversation_with_history():
    c = Conversation("系统提示词", 60000)
    c.add_user("写个文件")
    c.add_assistant(
        None, [ToolCall("c1", "write_file", {"path": "a.txt", "content": "hi"})]
    )
    c.add_tool_result("c1", "write_file", "已写入")
    c.add_assistant("完成", [])
    return c


def test_save_and_load_roundtrip(tmp_path):
    store = SessionStore(str(tmp_path))
    conv = _conversation_with_history()
    store.save("task1", conv)

    loaded = store.load("task1", 60000)
    assert loaded.messages == conv.messages
    assert loaded.system_prompt == conv.system_prompt
    # 载入后仍可继续追加消息（会话可延续）
    loaded.add_user("继续")
    assert loaded.messages[-1]["content"] == "继续"


def test_list_names_and_exists(tmp_path):
    store = SessionStore(str(tmp_path))
    store.save("a", _conversation_with_history())
    store.save("b", _conversation_with_history())
    assert store.list_names() == ["a", "b"]
    assert store.exists("a") and store.exists("b")
    assert not store.exists("c")


def test_rejects_illegal_name(tmp_path):
    store = SessionStore(str(tmp_path))
    try:
        store.save("../evil", _conversation_with_history())
    except ValueError:
        return
    raise AssertionError("应拒绝含路径分隔符的非法会话名")


def test_delete_removes_session(tmp_path):
    store = SessionStore(str(tmp_path))
    store.save("a", _conversation_with_history())
    assert store.exists("a")
    assert store.delete("a") is True
    assert not store.exists("a")
    # 删除不存在的会话返回 False
    assert store.delete("a") is False


def test_delete_illegal_name_returns_false(tmp_path):
    store = SessionStore(str(tmp_path))
    assert store.delete("../evil") is False
