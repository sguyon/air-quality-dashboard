"""The Docker files agree with the Procfile, keep keys and the home's config out of the image, and publish only from main.
Plain text checks (no YAML parser in the dev dependencies); the image itself is tested by hand (DEPLOYMENT.md, "Docker")."""
import json
import re
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def gunicorn_args(cmd):
    """gunicorn's flags without the bind address, which differs on purpose ($PORT on hosts, 8000 in the container)."""
    args = cmd[cmd.index("gunicorn"):]
    i = args.index("--bind")
    return args[:i] + args[i + 2:]


def test_image_runs_the_procfile_command_on_the_hosts_port():
    """Railway builds the Dockerfile and routes to its PORT: the image listens there, and on 8000 without one."""
    procfile = shlex.split(read("Procfile").split(":", 1)[1])
    shell = json.loads(re.search(r"^CMD (\[.*\])$", read("Dockerfile"), re.M).group(1))
    assert shell[:2] == ["sh", "-c"]
    cmd = shlex.split(shell[2])
    assert cmd[0] == "exec"
    assert gunicorn_args(cmd) == gunicorn_args(procfile)
    assert cmd[cmd.index("--bind") + 1] == "0.0.0.0:${PORT:-8000}"
    assert "${PORT:-8000}/health" in read("Dockerfile")   # the HEALTHCHECK asks the same port
    assert re.search(r"^EXPOSE 8000$", read("Dockerfile"), re.M)


def test_image_uses_the_repo_python_and_runs_as_a_user():
    dockerfile = read("Dockerfile")
    assert re.search(rf"^FROM python:{re.escape(read('.python-version').strip())}-slim-bookworm$", dockerfile, re.M)
    assert re.search(r"^USER (?!root\b)\S+$", dockerfile, re.M)
    assert "requirements-dev" not in dockerfile
    assert "/health" in dockerfile   # the HEALTHCHECK


def test_image_carries_its_commit_for_the_build_stamp():
    """image.yml passes the commit as GIT_SHA; the Dockerfile hands it to server.get_build_info as GIT_COMMIT_SHA."""
    dockerfile = read("Dockerfile")
    assert re.search(r'^ARG GIT_SHA=""$', dockerfile, re.M)
    assert re.search(r"^ENV GIT_COMMIT_SHA=\$GIT_SHA$", dockerfile, re.M)
    assert 'os.environ.get("GIT_COMMIT_SHA")' in read("server.py")
    assert "build-args: GIT_SHA=${{ github.sha }}" in read(".github/workflows/image.yml")


def test_a_missing_config_falls_back_like_on_a_computer():
    """CONFIG_FILE makes a missing file an error; the image links config.toml to the volume instead, so with nothing
    mounted it opens the demo."""
    dockerfile = read("Dockerfile")
    assert "ln -s /config/config.toml /app/config.toml" in dockerfile
    assert not re.search(r"^ENV\b.*CONFIG_FILE", dockerfile, re.M)


def test_dockerignore_keeps_keys_config_and_private_files_out():
    lines = {l.strip() for l in read(".dockerignore").splitlines() if l.strip() and not l.startswith("#")}
    for pattern in (".env", ".env*", "**/.env*", "config.toml", "**/config.toml", "internal/", "tests/", "docs/", "public/", ".git"):
        assert pattern in lines, pattern
    assert "!demo/config.toml" in lines   # the demo's config ships with the code
    assert not any(l.startswith("!") and ("env" in l or l.lstrip("!") == "config.toml") for l in lines)


def test_compose_is_local_only_with_optional_keys_and_a_read_only_config():
    compose = read("docker-compose.yml")
    assert '- "127.0.0.1:8000:8000"' in compose
    # only config.toml, and a missing one is an error rather than a folder Docker creates in its place
    assert re.search(r"- type: bind\n\s+source: \./config\.toml\n\s+target: /config/config\.toml\n\s+read_only: true\n"
                     r"\s+bind:\n\s+create_host_path: false\n", compose)
    assert re.search(r"- path: \.env\n\s+required: false", compose)
    assert "restart: unless-stopped" in compose
    assert "build: ." in compose


def test_image_workflow_publishes_only_from_main():
    wf = read(".github/workflows/image.yml")
    on = re.search(r"^on:\n(.*?)^\S", wf, re.M | re.S).group(1)
    assert re.findall(r"^  (\w+):", on, re.M) == ["push", "workflow_dispatch"]   # never pull_request
    assert "branches: [main]" in on
    assert "github.ref == 'refs/heads/main'" in wf
    assert re.search(r"^permissions:\n  contents: read\n  packages: write\n", wf, re.M)
    assert set(re.findall(r"secrets\.(\w+)", wf)) == {"GITHUB_TOKEN"}
    assert "platforms: linux/amd64,linux/arm64" in wf
    assert "ghcr.io/sguyon/home-air-quality:latest" in wf
    assert "ghcr.io/sguyon/home-air-quality:${{ github.sha }}" in wf
    assert "org.opencontainers.image.source=https://github.com/sguyon/home-air-quality" in wf
