from coding_agent.config import Config
from coding_agent.tools import build_registry


def _registry(tmp_path):
    cfg = Config(api_key="x", workspace=str(tmp_path), command_timeout=10)
    return build_registry(cfg)


def test_write_and_read_roundtrip(tmp_path):
    reg = _registry(tmp_path)
    out = reg.execute("write_file", {"path": "d/a.txt", "content": "hello\nworld\n"})
    assert "已写入" in out
    read = reg.execute("read_file", {"path": "d/a.txt"})
    assert "hello" in read and "world" in read


def test_read_file_numbered_lines(tmp_path):
    (tmp_path / "f.txt").write_text("a\nb\nc\n")
    reg = _registry(tmp_path)
    out = reg.execute("read_file", {"path": "f.txt"})
    assert "1 | a" in out and "3 | c" in out


def test_read_file_line_range(tmp_path):
    (tmp_path / "f.txt").write_text("a\nb\nc\nd\n")
    reg = _registry(tmp_path)
    out = reg.execute("read_file", {"path": "f.txt", "start_line": 2, "end_line": 3})
    assert "2 | b" in out and "3 | c" in out
    assert "1 | a" not in out


def test_edit_file_replaces(tmp_path):
    (tmp_path / "f.py").write_text("x = 1\nprint(x)\n")
    reg = _registry(tmp_path)
    reg.execute("edit_file", {"path": "f.py", "old_string": "x = 1", "new_string": "x = 2"})
    assert (tmp_path / "f.py").read_text() == "x = 2\nprint(x)\n"


def test_edit_file_not_found(tmp_path):
    (tmp_path / "f.py").write_text("abc")
    reg = _registry(tmp_path)
    out = reg.execute("edit_file", {"path": "f.py", "old_string": "zzz", "new_string": "y"})
    assert "未找到" in out


def test_edit_file_ambiguous(tmp_path):
    (tmp_path / "f.py").write_text("a = 1\na = 1\n")
    reg = _registry(tmp_path)
    out = reg.execute("edit_file", {"path": "f.py", "old_string": "a = 1", "new_string": "b"})
    assert "唯一" in out or "2 次" in out


def test_path_escape_rejected(tmp_path):
    reg = _registry(tmp_path)
    out = reg.execute("write_file", {"path": "../escape.txt", "content": "x"})
    assert "越界" in out
    assert not (tmp_path.parent / "escape.txt").exists()


def test_run_command(tmp_path):
    reg = _registry(tmp_path)
    out = reg.execute("run_command", {"command": "echo hello"})
    assert "hello" in out


def test_run_command_timeout(tmp_path):
    # Windows 下用 python 睡眠模拟超时（timeout=0 秒会立即超时）
    cfg = Config(api_key="x", workspace=str(tmp_path), command_timeout=1)
    reg = build_registry(cfg)
    out = reg.execute("run_command", {"command": "python -c \"import time; time.sleep(5)\""})
    assert "超时" in out or "退出码" in out


def test_unknown_tool(tmp_path):
    reg = _registry(tmp_path)
    out = reg.execute("nope", {})
    assert "未知工具" in out


def test_list_directory(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "sub").mkdir()
    reg = _registry(tmp_path)
    out = reg.execute("list_directory", {})
    assert "a.py" in out and "sub" in out
