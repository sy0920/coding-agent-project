from coding_agent.cli import _format_step


def test_format_read_file_hides_body():
    result = "文件 numbers.txt（共 5 行，显示 1-5 行）\n    1 | 12\n    2 | 7\n"
    out = _format_step("read_file", {"path": "numbers.txt"}, result)
    assert "numbers.txt" in out
    assert "共 5 行" in out
    assert "|" not in out  # 正文行号不应出现


def test_format_write_file_shows_size_not_content():
    content = "x" * 1000
    out = _format_step("write_file", {"path": "a.py", "content": content}, "已写入 a.py（1000 字符）")
    assert "a.py" in out
    assert "1000 字符" in out
    assert "x" * 500 not in out  # 不打印正文


def test_format_edit_file_shows_diff():
    out = _format_step(
        "edit_file",
        {"path": "a.py", "old_string": "x = 1", "new_string": "x = 2"},
        "已替换 1 处。文件：a.py",
    )
    assert "- x = 1" in out
    assert "+ x = 2" in out


def test_format_error_marked():
    out = _format_step("read_file", {"path": "nope.txt"}, "错误：文件不存在：nope.txt")
    assert "✗" in out
    assert "文件不存在" in out
