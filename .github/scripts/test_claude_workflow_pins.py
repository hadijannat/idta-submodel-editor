from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATHS = (
    REPO_ROOT / ".github" / "workflows" / "claude.yml",
    REPO_ROOT / ".github" / "workflows" / "claude-code-review.yml",
)
CLAUDE_ACTION_PATTERN = re.compile(r"uses:\s+anthropics/claude-code-action@([0-9a-f]{40})\b")


class ClaudeWorkflowPinTests(unittest.TestCase):
    def test_claude_workflows_share_one_pinned_action_sha(self) -> None:
        pinned_shas: dict[str, set[str]] = {}

        for workflow_path in WORKFLOW_PATHS:
            matches = set(CLAUDE_ACTION_PATTERN.findall(workflow_path.read_text()))
            self.assertTrue(matches, f"{workflow_path} does not pin anthropics/claude-code-action.")
            pinned_shas[workflow_path.name] = matches

        for workflow_name, matches in pinned_shas.items():
            self.assertEqual(
                len(matches),
                1,
                f"{workflow_name} should use one shared anthropics/claude-code-action SHA.",
            )

        self.assertEqual(
            len({next(iter(matches)) for matches in pinned_shas.values()}),
            1,
            "Claude workflows should stay on the same anthropics/claude-code-action SHA.",
        )


if __name__ == "__main__":
    unittest.main()
