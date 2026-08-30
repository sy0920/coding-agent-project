from coding_agent import cli
from coding_agent.cli import _clean_title, _format_step, _make_step_printer, _paint


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


def test_format_write_file_rejected_not_shown_as_written():
    """write_file 被审批拒绝时，应标记 ✗ 拒绝，而非误显示成「已写入 N 字符」。"""
    out = _format_step(
        "write_file",
        {"path": "a.py", "content": "x = 1"},
        "用户拒绝了该操作，未执行。",
    )
    assert "✗" in out
    assert "拒绝" in out
    assert "字符" not in out  # 不应显示「已写入 N 字符」


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


def test_format_multi_line_result_keeps_newlines():
    """todo / list_directory 等多行结果应真正换行，而非显示字面 \\n。"""
    result = "当前任务清单：\n1. 写代码\n2. 测试"
    out = _format_step("todo", {"todos": ["x"]}, result)
    assert "当前任务清单：" in out
    assert "1. 写代码" in out
    assert "2. 测试" in out
    assert "\\n" not in out  # 不再出现字面反斜杠 n


def test_finish_step_does_not_duplicate_summary(capsys):
    """finish 事件只打印简短标记，完整总结由 result.final_answer 打印一次。"""
    step = _make_step_printer()
    step("finish", {"summary": "完成啦"}, "任务已结束")
    out = capsys.readouterr().out
    assert "✓ 任务完成" in out
    assert "完成啦" not in out


def test_clean_title_strips_illegal_chars():
    assert _clean_title("统计词频") == "统计词频"
    assert _clean_title('"统计词频"') == "统计词频"
    assert _clean_title("a/b\\c:d") == "abcd"
    assert _clean_title("a<b>c|d?e*f") == "abcdef"
    assert _clean_title("标题\n换行\t制表") == "标题换行制表"


def test_clean_title_fallback_and_truncate():
    assert _clean_title("") == "default"
    assert _clean_title("   ") == "default"
    assert _clean_title('""') == "default"
    long = _clean_title("这是一个非常非常非常非常非常长的标题，超过二十四个字符就会被截断处理")
    assert len(long) <= 24
