import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
EVALS = ROOT / "evals"


def _golden_prompts() -> list[dict[str, str]]:
    text = (EVALS / "golden.yaml").read_text(encoding="utf-8")
    prompts: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        id_match = re.match(r"- id: (q\d+)", line)
        if id_match:
            current = {"id": id_match.group(1)}
            prompts.append(current)
            continue
        tool_match = re.match(r"\s+expected_tool: ([\w-]+)", line)
        if current is not None and tool_match:
            current["expected_tool"] = tool_match.group(1)
    return prompts


def test_golden_prompt_ids_are_unique_and_docs_match_count() -> None:
    prompts = _golden_prompts()
    ids = [prompt["id"] for prompt in prompts]
    assert len(ids) == len(set(ids))
    assert len(prompts) == 27

    readme = (EVALS / "README.md").read_text(encoding="utf-8")
    rubric = (EVALS / "rubric.md").read_text(encoding="utf-8")
    assert "27 prompts" in readme
    assert "27 golden prompts" in rubric
    assert not re.search(r"\b20 prompts\b", readme + rubric)


def test_eval_expected_tools_exist() -> None:
    from anthropic_news_mcp.server import mcp

    tools = {tool.name for tool in mcp._tool_manager.list_tools()}  # noqa: SLF001
    for prompt in _golden_prompts():
        expected = prompt.get("expected_tool")
        assert expected == "any" or expected in tools


def test_offline_eval_cases_are_valid() -> None:
    sys.path.insert(0, str(EVALS))
    from run_offline_eval import load_cases

    from anthropic_news_mcp.server import mcp

    tools = {tool.name for tool in mcp._tool_manager.list_tools()}  # noqa: SLF001
    cases = load_cases()
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    for case in cases:
        assert case["tool"] in tools
        assert isinstance(case.get("args", {}), dict)
        assert any(
            key in case
            for key in ("min_items", "response_contains", "error_contains", "item_source_keys")
        )
