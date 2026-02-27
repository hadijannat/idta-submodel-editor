"""Regression tests for review process artifacts."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_pr_template_uses_repo_root_runnable_frontend_commands():
    content = _read(".github/pull_request_template.md")

    assert "npm --prefix frontend run lint" in content
    assert "npm --prefix frontend run type-check" in content
    assert "npm --prefix frontend run test:unit" in content
    assert "E2E_PROFILE=magic-import npm --prefix frontend run test:e2e" in content
    assert "E2E_PROFILE=dataspace npm --prefix frontend run test:e2e" in content
    assert "E2E_PROFILE=plc npm --prefix frontend run test:e2e" in content

    assert "`npm run lint`" not in content
    assert "`npm run type-check`" not in content
    assert "`npm run test:unit`" not in content


def test_security_artifacts_require_private_reporting_hygiene():
    security_template = _read(".github/ISSUE_TEMPLATE/security_review.md")
    security_policy = _read(".github/SECURITY.md")

    assert "Public issue warning" in security_template
    assert "private reporting" in security_template.lower()
    assert "Reproduction / proof" not in security_template
    assert "Public-safe observations" in security_template

    assert "Reporting a Vulnerability" in security_policy
    assert "security/advisories/new" in security_policy


def test_docs_workflow_validates_docs_on_pull_requests_without_deploying():
    workflow = _read(".github/workflows/docs.yml")

    assert "pull_request:" in workflow
    assert "mkdocs build --strict" in workflow
    assert (
        "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" in workflow
    )


def test_ci_workflow_avoids_duplicate_push_and_pull_request_runs():
    workflow = _read(".github/workflows/ci.yml")

    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "pull_request:" in workflow


def test_review_playbook_documents_branch_protection_prerequisite():
    playbook = _read("docs/reference/review-playbook.md")

    assert "Deployment Governance Prerequisite" in playbook
    assert "branch protection/rulesets on `main`" in playbook
