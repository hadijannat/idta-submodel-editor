#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.request import Request, urlopen


ZERO_SHA = "0" * 40


def fetch_json(url: str, token: str | None) -> Any:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request) as response:  # noqa: S310 - GitHub API endpoint is fixed by the workflow
        return json.load(response)


def collect_pull_request_files(
    repository: str,
    pull_request_number: int,
    token: str | None,
    fetcher: Callable[[str, str | None], Any] = fetch_json,
) -> list[str]:
    page = 1
    changed_files: list[str] = []

    while True:
        url = (
            f"https://api.github.com/repos/{repository}/pulls/{pull_request_number}/files"
            f"?per_page=100&page={page}"
        )
        payload = fetcher(url, token)
        if not payload:
            break

        changed_files.extend(item["filename"] for item in payload)
        if len(payload) < 100:
            break
        page += 1

    return changed_files


def collect_push_files(
    repository: str,
    payload: dict[str, Any],
    token: str | None,
    fetcher: Callable[[str, str | None], Any] = fetch_json,
) -> list[str]:
    before = payload.get("before", "")
    after = payload.get("after") or os.environ.get("GITHUB_SHA", "")

    if before and before != ZERO_SHA:
        compare_url = f"https://api.github.com/repos/{repository}/compare/{before}...{after}"
        compare_payload = fetcher(compare_url, token)
        return [item["filename"] for item in compare_payload.get("files", [])]

    changed_files: set[str] = set()
    for commit in payload.get("commits", []):
        for key in ("added", "modified", "removed"):
            changed_files.update(commit.get(key, []))

    if changed_files:
        return sorted(changed_files)

    if after:
        commit_url = f"https://api.github.com/repos/{repository}/commits/{after}"
        commit_payload = fetcher(commit_url, token)
        return sorted(item["filename"] for item in commit_payload.get("files", []))

    return []


def classify_changed_files(changed_files: Iterable[str]) -> dict[str, bool]:
    outputs = {
        "backend": False,
        "frontend": False,
        "frontend_lockfile": False,
        "plc4x": False,
        "docker": False,
        "workflows": False,
    }

    for file_path in changed_files:
        if file_path.startswith("backend/"):
            outputs["backend"] = True
        if file_path.startswith("frontend/"):
            outputs["frontend"] = True
        if file_path in {"frontend/package.json", "frontend/package-lock.json"}:
            outputs["frontend_lockfile"] = True
        if file_path.startswith("plc4x-bridge/"):
            outputs["plc4x"] = True
        if file_path in {
            "backend/Dockerfile",
            "frontend/Dockerfile",
            "plc4x-bridge/Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
        } or file_path.startswith("docker-compose."):
            outputs["docker"] = True
        if file_path.startswith(".github/workflows/") or file_path.startswith(".github/actions/") or file_path.startswith(
            ".github/scripts/"
        ):
            outputs["workflows"] = True

    return outputs


def determine_changed_files(
    event_name: str,
    repository: str,
    payload: dict[str, Any],
    token: str | None,
    fetcher: Callable[[str, str | None], Any] = fetch_json,
) -> list[str]:
    if event_name in {"pull_request", "pull_request_target"}:
        number = payload.get("number") or payload.get("pull_request", {}).get("number")
        if not number:
            raise RuntimeError("Missing pull request number in event payload.")
        return collect_pull_request_files(repository, int(number), token, fetcher)
    if event_name == "push":
        return collect_push_files(repository, payload, token, fetcher)
    raise RuntimeError(f"Unsupported event name: {event_name}")


def write_outputs(output_path: Path, outputs: dict[str, bool]) -> None:
    with output_path.open("a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={str(value).lower()}\n")


def main() -> int:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    token = os.environ.get("GITHUB_TOKEN")

    if not event_name or not repository or not event_path:
        raise RuntimeError("GITHUB_EVENT_NAME, GITHUB_REPOSITORY, and GITHUB_EVENT_PATH are required.")

    payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    changed_files = determine_changed_files(event_name, repository, payload, token)

    if changed_files:
        print("Changed files:")
        for file_path in changed_files:
            print(file_path)
    else:
        print("Changed files:\n<none>")

    outputs = classify_changed_files(changed_files)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        write_outputs(Path(output_path), outputs)
    else:
        for key, value in outputs.items():
            print(f"{key}={str(value).lower()}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
