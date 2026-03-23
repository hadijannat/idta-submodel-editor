from __future__ import annotations

import functools
import re
import unittest
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATHS = (
    REPO_ROOT / ".github" / "workflows" / "claude.yml",
    REPO_ROOT / ".github" / "workflows" / "claude-code-review.yml",
)
CLAUDE_ACTION_PATTERN = re.compile(r"uses:\s+anthropics/claude-code-action@([0-9a-f]{40})\b")
ACTION_METADATA_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/anthropics/claude-code-action/{sha}/action.yml"
)


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _extract_shared_sha() -> str:
    pinned_shas: dict[str, set[str]] = {}

    for workflow_path in WORKFLOW_PATHS:
        matches = set(CLAUDE_ACTION_PATTERN.findall(workflow_path.read_text()))
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
    lines = workflow_path.read_text().splitlines()
    used_inputs: set[str] = set()
    line_index = 0

    while line_index < len(lines):
        line = lines[line_index]
        match = CLAUDE_ACTION_PATTERN.search(line)
        if not match:
            line_index += 1
            continue

        uses_indent = _indent_width(line)
        line_index += 1

        while line_index < len(lines):
            line = lines[line_index]
            stripped = line.strip()
            indent = _indent_width(line)

            if stripped.startswith("- ") and indent <= uses_indent:
                break

            if stripped == "with:" and indent > uses_indent:
                with_indent = indent
                key_indent: int | None = None
                line_index += 1

                while line_index < len(lines):
                    line = lines[line_index]
                    stripped = line.strip()
                    indent = _indent_width(line)

                    if stripped and indent <= with_indent:
                        break

                    if not stripped:
                        line_index += 1
                        continue

                    if key_indent is None and indent > with_indent:
                        key_indent = indent

                    if key_indent is not None and indent == key_indent:
                        key_match = re.match(r"([A-Za-z_][A-Za-z0-9_-]*):", stripped)
                        if key_match:
                            used_inputs.add(key_match.group(1))

                    line_index += 1

                continue

            line_index += 1

    return used_inputs


@functools.lru_cache(maxsize=1)
def _fetch_supported_inputs(sha: str) -> set[str]:
    url = ACTION_METADATA_URL_TEMPLATE.format(sha=sha)
    with urllib.request.urlopen(url, timeout=10) as response:
        action_metadata = response.read().decode("utf-8")

    lines = action_metadata.splitlines()
    input_names: set[str] = set()
    inputs_indent: int | None = None
    key_indent: int | None = None

    for line in lines:
        stripped = line.strip()
        indent = _indent_width(line)

        if inputs_indent is None:
            if stripped == "inputs:":
                inputs_indent = indent
            continue

        if not stripped:
            continue

        if indent <= inputs_indent:
            break

        if key_indent is None and indent > inputs_indent:
            key_indent = indent

        if key_indent is not None and indent == key_indent:
            key_match = re.match(r"([A-Za-z_][A-Za-z0-9_-]*):$", stripped)
            if key_match:
                input_names.add(key_match.group(1))

    if not input_names:
        raise AssertionError(f"Failed to parse inputs from {url}.")

    return input_names


class ClaudeWorkflowPinTests(unittest.TestCase):
    def test_claude_workflows_share_one_pinned_action_sha(self) -> None:
        self.assertRegex(_extract_shared_sha(), r"^[0-9a-f]{40}$")

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
