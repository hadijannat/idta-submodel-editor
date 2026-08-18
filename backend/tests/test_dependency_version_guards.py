from pathlib import Path

from packaging.specifiers import SpecifierSet


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _declared_anthropic_specifier() -> tuple[str, SpecifierSet]:
    requirement = next(
        line.strip()
        for line in (REPOSITORY_ROOT / "backend" / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip().startswith("anthropic")
    )
    specifier_text = requirement.removeprefix("anthropic")
    return specifier_text, SpecifierSet(specifier_text)


def test_anthropic_guard_accepts_stable_versions_in_supported_range() -> None:
    _, supported_range = _declared_anthropic_specifier()
    assert supported_range.contains("0.122.0", prereleases=False)
    assert supported_range.contains("0.122.9", prereleases=False)


def test_anthropic_guard_rejects_prereleases_and_upper_boundary() -> None:
    _, supported_range = _declared_anthropic_specifier()
    assert not supported_range.contains("0.121.9", prereleases=False)
    assert not supported_range.contains("0.122.0rc1", prereleases=False)
    assert not supported_range.contains("1.0.0a1", prereleases=False)
    assert not supported_range.contains("1.0.0", prereleases=False)


def test_ci_guard_uses_the_declared_anthropic_specifier() -> None:
    specifier_text, _ = _declared_anthropic_specifier()
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert f'SpecifierSet("{specifier_text}")' in workflow
    assert "supported_range.contains(anthropic_version, prereleases=False)" in workflow
