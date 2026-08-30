from coding_agent import cli
from coding_agent.cli import _format_step, _paint


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


def test_format_edit_file_multiline_diff_keeps_each_line():
    """多行改动按行展示，每行带 -/+ 前缀，而非压成单行。"""
    old = "a = 1\nb = 2\nc = 3"
    new = "a = 1\nb = 99\nc = 3"
    out = _format_step(
        "edit_file",
        {"path": "a.py", "old_string": old, "new_string": new},
        "已替换 1 处。",
    )
    assert "- a = 1" in out
    assert "- c = 3" in out
    assert "+ b = 99" in out
    assert out.count("\n") >= 5  # 每行独立成行


def test_paint_off_when_no_color():
    # 测试环境下 stdout 非 tty → 颜色默认关闭，原样返回
    assert _paint("31", "hi") == "hi"


def test_paint_wraps_when_color_enabled(monkeypatch):
    monkeypatch.setattr(cli, "_USE_COLOR", True)
    assert _paint("31", "hi") == "\x1b[31mhi\x1b[0m"


def test_format_compact_shows_token_change():
    out = _format_step(
        "compact", {"before": 12000, "after": 3400}, "较早的历史已压缩为摘要"
    )
    assert "压缩" in out
    assert "12000" in out
    assert "3400" in out
