from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return self.payload


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

    def test_fetch_json_retries_transient_github_failures(self) -> None:
        responses = [
            self.module.URLError("temporary network reset"),
            FakeResponse(b'{"ok": true}'),
        ]

        def fake_urlopen(_request, timeout):
            self.assertEqual(timeout, 10)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        stderr = StringIO()
        with (
            redirect_stderr(stderr),
            patch.object(self.module, "urlopen", side_effect=fake_urlopen),
            patch.object(self.module.time, "sleep") as sleep_mock,
        ):
            payload = self.module.fetch_json(
                "https://api.github.com/repos/example/repo",
                "token",
                attempts=2,
                backoff_seconds=0,
            )

        self.assertEqual(payload, {"ok": True})
        self.assertIn("retrying", stderr.getvalue())
        sleep_mock.assert_called_once_with(0)

    def test_warn_if_unauthenticated_makes_rate_limit_risk_visible(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr):
            self.module.warn_if_unauthenticated(None)

        self.assertIn("GITHUB_TOKEN is unset", stderr.getvalue())

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

    def test_extract_filenames_includes_previous_filename_for_renames(self) -> None:
        """Cross-directory renames must trigger CI for both source and destination."""
        payload = [
            {
                "filename": "frontend/src/App.tsx",
                "previous_filename": "backend/app/App.py",
                "status": "renamed",
            }
        ]
        self.assertEqual(
            sorted(self.module._extract_filenames(payload)),
            ["backend/app/App.py", "frontend/src/App.tsx"],
        )

        outputs = self.module.classify_changed_files(
            self.module._extract_filenames(payload)
        )
        self.assertTrue(outputs["backend"], "rename source must flip backend flag")
        self.assertTrue(outputs["frontend"], "rename destination must flip frontend flag")


if __name__ == "__main__":
    unittest.main()
