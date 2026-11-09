"""The public repo never points to or contains the private notes folder."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_no_tracked_file_points_to_research():
    # this file and the CI workflow name the old folder on purpose, to forbid it
    hits = git("grep", "-l", "research/", "--", ".", ":!tests/test_repo_hygiene.py", ":!.github/workflows/ci.yml").stdout
    assert hits.strip() == ""


def test_internal_is_ignored():
    assert git("check-ignore", "-q", "internal/ROADMAP.md").returncode == 0


def test_nothing_private_is_tracked():
    tracked = git("ls-files").stdout.split()
    assert not [f for f in tracked if f.startswith(("internal/", "research/", "build-log/")) or f in ("config.toml", ".env")]


def test_demo_config_is_tracked_and_the_home_config_is_not():
    """Only the root config.toml (someone's home) is private; the demo's config ships with the code."""
    assert "demo/config.toml" in git("ls-files", "demo").stdout.split()
    assert git("check-ignore", "-q", "demo/config.toml").returncode == 1
    assert git("check-ignore", "-q", "config.toml").returncode == 0
