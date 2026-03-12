from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("compute_changed_paths.py")
    spec = importlib.util.spec_from_file_location("compute_changed_paths", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load compute_changed_paths module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComputeChangedPathsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_classify_changed_files_sets_expected_outputs(self) -> None:
        outputs = self.module.classify_changed_files(
            [
                "backend/app/main.py",
                "frontend/package-lock.json",
                "plc4x-bridge/src/App.java",
                "docker-compose.dev.yml",
                ".github/scripts/compute_changed_paths.py",
            ]
        )

        self.assertEqual(
            outputs,
            {
                "backend": True,
                "frontend": True,
                "frontend_lockfile": True,
                "plc4x": True,
                "docker": True,
                "workflows": True,
            },
        )

    def test_collect_pull_request_files_paginates(self) -> None:
        responses = [
            [{"filename": "backend/app/main.py"}] * 100,
            [{"filename": "frontend/src/App.tsx"}],
        ]

        def fake_fetcher(url: str, token: str | None):
            self.assertIn("pulls/115/files", url)
            return responses.pop(0)

        changed_files = self.module.collect_pull_request_files(
            "hadijannat/idta-submodel-editor",
            115,
            "token",
            fake_fetcher,
        )

        self.assertEqual(len(changed_files), 101)
        self.assertEqual(changed_files[-1], "frontend/src/App.tsx")

    def test_collect_push_files_uses_compare_when_before_is_available(self) -> None:
        def fake_fetcher(url: str, token: str | None):
            self.assertIn("/compare/", url)
            return {"files": [{"filename": "frontend/package.json"}, {"filename": "docker-compose.yaml"}]}

        changed_files = self.module.collect_push_files(
            "hadijannat/idta-submodel-editor",
            {"before": "a" * 40, "after": "b" * 40},
            "token",
            fake_fetcher,
        )

        self.assertEqual(changed_files, ["frontend/package.json", "docker-compose.yaml"])

    def test_collect_push_files_uses_commit_lists_when_before_is_zero(self) -> None:
        changed_files = self.module.collect_push_files(
            "hadijannat/idta-submodel-editor",
            {
                "before": self.module.ZERO_SHA,
                "after": "b" * 40,
                "commits": [
                    {"added": ["backend/new.py"], "modified": ["frontend/package-lock.json"], "removed": []},
                    {"added": [], "modified": [".github/workflows/ci.yml"], "removed": ["docker-compose.yaml"]},
                ],
            },
            "token",
        )

        self.assertEqual(
            changed_files,
            [
                ".github/workflows/ci.yml",
                "backend/new.py",
                "docker-compose.yaml",
                "frontend/package-lock.json",
            ],
        )

    def test_determine_changed_files_requires_supported_event(self) -> None:
        with self.assertRaises(RuntimeError):
            self.module.determine_changed_files("schedule", "hadijannat/idta-submodel-editor", {}, None)


if __name__ == "__main__":
    unittest.main()
