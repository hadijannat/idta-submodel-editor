from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "codeql.yml"
EXPECTED_ACTIONS = {"init", "autobuild", "analyze"}
CODEQL_ACTION_PATTERN = re.compile(
    r"^\s*uses:\s+github/codeql-action/(init|autobuild|analyze)@([0-9a-f]{40})\s+#"
)


def _extract_codeql_shas() -> dict[str, str]:
    pinned_actions = {
        action: sha
        for line in WORKFLOW_PATH.read_text().splitlines()
        if (match := CODEQL_ACTION_PATTERN.match(line)) is not None
        for action, sha in [match.groups()]
    }
    if set(pinned_actions) != EXPECTED_ACTIONS:
        raise AssertionError(
            "codeql.yml must pin exactly init, autobuild, and analyze actions."
        )
    return pinned_actions


class CodeQLWorkflowPinTests(unittest.TestCase):
    def test_codeql_actions_share_one_pinned_sha(self) -> None:
        pinned_actions = _extract_codeql_shas()
        self.assertEqual(len(set(pinned_actions.values())), 1)
        self.assertTrue(
            re.fullmatch(r"[0-9a-f]{40}", next(iter(pinned_actions.values())))
        )


if __name__ == "__main__":
    unittest.main()
