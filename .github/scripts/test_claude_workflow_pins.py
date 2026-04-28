from __future__ import annotations

import functools
import os
import re
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs yamllint, which brings PyYAML.
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATHS = (
    REPO_ROOT / ".github" / "workflows" / "claude.yml",
    REPO_ROOT / ".github" / "workflows" / "claude-code-review.yml",
)
ACTION_METADATA_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/anthropics/claude-code-action/{sha}/action.yml"
)
CLAUDE_ACTION_USES_PATTERN = re.compile(
    r"^anthropics/claude-code-action@([0-9a-f]{40})$"
)


def _load_yaml_mapping(text: str, source: str) -> dict[str, Any]:
    if yaml is None:
        raise unittest.SkipTest("PyYAML is required to parse workflow YAML.")

    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise AssertionError(f"{source} did not parse as a YAML mapping.")
    return loaded


def _iter_workflow_steps(workflow: dict[str, Any]):
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return

    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict):
                yield step


def _claude_action_sha(step: dict[str, Any]) -> str | None:
    uses = step.get("uses")
    if not isinstance(uses, str):
        return None
    match = CLAUDE_ACTION_USES_PATTERN.match(uses)
    return match.group(1) if match else None


def _extract_action_shas(workflow_path: Path) -> set[str]:
    workflow = _load_yaml_mapping(workflow_path.read_text(), str(workflow_path))
    return {
        sha
        for step in _iter_workflow_steps(workflow)
        if (sha := _claude_action_sha(step)) is not None
    }


def _extract_shared_sha() -> str:
    pinned_shas: dict[str, set[str]] = {}

    for workflow_path in WORKFLOW_PATHS:
        matches = _extract_action_shas(workflow_path)
        if not matches:
            raise AssertionError(f"{workflow_path} does not pin anthropics/claude-code-action.")
        pinned_shas[workflow_path.name] = matches

    for workflow_name, matches in pinned_shas.items():
        if len(matches) != 1:
            raise AssertionError(
                f"{workflow_name} should use one shared anthropics/claude-code-action SHA."
            )

    shared_shas = {next(iter(matches)) for matches in pinned_shas.values()}
    if len(shared_shas) != 1:
        raise AssertionError(
            "Claude workflows should stay on the same anthropics/claude-code-action SHA."
        )

    return next(iter(shared_shas))


def _extract_used_inputs(workflow_path: Path) -> set[str]:
    workflow = _load_yaml_mapping(workflow_path.read_text(), str(workflow_path))
    used_inputs: set[str] = set()
    for step in _iter_workflow_steps(workflow):
        if _claude_action_sha(step) is None:
            continue
        with_block = step.get("with", {})
        if not isinstance(with_block, dict):
            raise AssertionError(
                f"{workflow_path.name} has a Claude action step with a non-mapping with: block."
            )
        used_inputs.update(str(key) for key in with_block)

    return used_inputs


@functools.lru_cache(maxsize=1)
def _fetch_supported_inputs(sha: str) -> set[str]:
    url = ACTION_METADATA_URL_TEMPLATE.format(sha=sha)
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            action_metadata = response.read().decode("utf-8")
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise AssertionError(
            "Network-dependent Claude action metadata check failed while fetching "
            f"{url}: {exc}. Retry CI or verify the pinned action inputs manually."
        ) from exc

    metadata = _load_yaml_mapping(action_metadata, url)
    inputs = metadata.get("inputs", {})
    if not isinstance(inputs, dict):
        raise AssertionError(f"Failed to parse inputs from {url}.")

    input_names = {str(name) for name in inputs}
    if not input_names:
        raise AssertionError(f"Failed to parse inputs from {url}.")

    return input_names


class ClaudeWorkflowPinTests(unittest.TestCase):
    def test_claude_workflows_share_one_pinned_action_sha(self) -> None:
        self.assertRegex(_extract_shared_sha(), r"^[0-9a-f]{40}$")

    def test_claude_workflow_inputs_are_parseable(self) -> None:
        for workflow_path in WORKFLOW_PATHS:
            self.assertTrue(_extract_used_inputs(workflow_path))

    @unittest.skipUnless(
        os.environ.get("CI") or os.environ.get("VERIFY_CLAUDE_ACTION_INPUTS"),
        "network-dependent upstream action metadata check; set VERIFY_CLAUDE_ACTION_INPUTS=1 to run locally",
    )
    def test_pinned_claude_action_supports_all_workflow_inputs(self) -> None:
        pinned_sha = _extract_shared_sha()
        supported_inputs = _fetch_supported_inputs(pinned_sha)

        for workflow_path in WORKFLOW_PATHS:
            used_inputs = _extract_used_inputs(workflow_path)
            missing_inputs = used_inputs - supported_inputs
            self.assertFalse(
                missing_inputs,
                (
                    f"{workflow_path.name} uses unsupported anthropics/claude-code-action inputs "
                    f"for {pinned_sha}: {sorted(missing_inputs)}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
