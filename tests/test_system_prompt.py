from coding_agent.system_prompt import build_system_prompt, load_project_instructions


def test_load_project_instructions_from_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("所有函数都要写 docstring", encoding="utf-8")
    assert "docstring" in load_project_instructions(str(tmp_path))


def test_load_project_instructions_fallback_to_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("使用 4 空格缩进", encoding="utf-8")
    assert "缩进" in load_project_instructions(str(tmp_path))


def test_load_project_instructions_none(tmp_path):
    assert load_project_instructions(str(tmp_path)) == ""


def test_build_system_prompt_injects_rules():
    p = build_system_prompt("/ws", "禁止使用 print")
    assert "禁止使用 print" in p
    assert "项目自定义规则" in p
