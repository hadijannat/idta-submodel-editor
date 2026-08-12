from packaging.specifiers import SpecifierSet


ANTHROPIC_SUPPORTED_RANGE = SpecifierSet(">=0.121.0,<1.0.0")


def test_anthropic_guard_accepts_stable_versions_in_supported_range() -> None:
    assert ANTHROPIC_SUPPORTED_RANGE.contains("0.121.0", prereleases=False)
    assert ANTHROPIC_SUPPORTED_RANGE.contains("0.121.9", prereleases=False)


def test_anthropic_guard_rejects_prereleases_and_upper_boundary() -> None:
    assert not ANTHROPIC_SUPPORTED_RANGE.contains("0.121.0rc1", prereleases=False)
    assert not ANTHROPIC_SUPPORTED_RANGE.contains("1.0.0a1", prereleases=False)
    assert not ANTHROPIC_SUPPORTED_RANGE.contains("1.0.0", prereleases=False)
