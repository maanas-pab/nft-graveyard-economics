"""The CI workflow is part of the product: it must parse and it must still
run the two promises this repo makes — the suite, and the payload gate."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def wf() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def triggers(wf: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True (YAML 1.1)
    return wf.get("on", wf.get(True))


def steps(wf: dict) -> list:
    return wf["jobs"]["test"]["steps"]


def step_named(wf: dict, name: str) -> dict:
    for s in steps(wf):
        if s.get("name") == name:
            return s
    raise AssertionError(f"missing workflow step: {name}")


def test_workflow_parses_and_triggers_on_push_and_pr(wf):
    assert wf["name"] == "ci"
    on = triggers(wf)
    assert on["push"]["branches"] == ["main"]
    assert "pull_request" in on


def test_workflow_still_runs_the_suite_and_the_payload_gate(wf):
    runs = [s.get("run", "") for s in steps(wf)]
    assert any("pytest" in r for r in runs), "CI no longer runs the tests"
    assert any("src.pipeline --web" in r for r in runs), "CI no longer rebuilds the payload"
    assert any("git diff" in r for r in runs), "CI no longer gates on reproducibility"
