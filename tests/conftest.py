"""
Pytest configuration for tests.

Configures anyio to only use asyncio backend (not trio).
Checks that the skill_seekers package is installed before running tests.
"""

import atexit
import os
import shutil
import stat
import sys
import tempfile

import pytest


def _prefer_interpreter_scripts_on_path():
    """Put the running interpreter's scripts dir first on PATH.

    Many e2e tests shell out to bare console scripts (``skill-seekers``,
    ``skill-seekers-estimate``...). When pytest runs as ``.venv/bin/python -m
    pytest`` without an activated venv, PATH resolves those names to whatever
    global install happens to exist (e.g. a pyenv shim for an older/newer
    release), so the tests exercise the wrong package. Pin them to the
    environment that is actually under test.
    """
    scripts_dir = os.path.dirname(sys.executable)
    path = os.environ.get("PATH", "")
    entries = path.split(os.pathsep) if path else []
    if entries[:1] != [scripts_dir]:
        os.environ["PATH"] = os.pathsep.join(
            [scripts_dir, *[e for e in entries if e != scripts_dir]]
        )


_prefer_interpreter_scripts_on_path()


def _stub_out_claude_cli():
    """Shadow the real ``claude`` CLI with a stub that refuses to run.

    The AI enhancers default to "auto" mode, which falls back to LOCAL mode
    (``claude --dangerously-skip-permissions <prompt>``) whenever
    ANTHROPIC_API_KEY is unset. On a developer machine with Claude Code
    installed, unmocked tests (e.g. PatternRecognizer(depth="deep")) would then
    launch real, permission-skipping model sessions -- slow, costly, and
    non-hermetic. CI has no ``claude`` binary, so there the enhancers just
    disable themselves; make every host behave the same way. Tests that mock
    subprocess are unaffected. Set SKILL_SEEKERS_TEST_REAL_CLAUDE=1 to opt out.
    """
    if os.name == "nt" or os.environ.get("SKILL_SEEKERS_TEST_REAL_CLAUDE") == "1":
        return
    stub_dir = tempfile.mkdtemp(prefix="ss-test-claude-stub-")
    atexit.register(shutil.rmtree, stub_dir, ignore_errors=True)
    stub = os.path.join(stub_dir, "claude")
    with open(stub, "w") as f:
        f.write(
            "#!/bin/sh\n"
            'echo "claude CLI is stubbed out in the skill-seekers test suite '
            '(SKILL_SEEKERS_TEST_REAL_CLAUDE=1 to allow)" >&2\n'
            "exit 127\n"
        )
    os.chmod(stub, os.stat(stub).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.environ["PATH"] = os.pathsep.join([stub_dir, os.environ.get("PATH", "")])


_stub_out_claude_cli()

# Python 3.14+ argparse colorizes --help when FORCE_COLOR is inherited from the
# launching terminal, which breaks the plain-text help assertions in the CLI
# tests. Keep stdlib output uncolored unless a caller explicitly opts in.
os.environ.setdefault("PYTHON_COLORS", "0")


def pytest_configure(config):  # noqa: ARG001
    """Check if package is installed before running tests."""
    try:
        import skill_seekers  # noqa: F401
    except ModuleNotFoundError:
        print("\n" + "=" * 70)
        print("ERROR: skill_seekers package not installed")
        print("=" * 70)
        print("\nPlease install the package in editable mode first:")
        print("  pip install -e .")
        print("\nOr activate your virtual environment if you already installed it.")
        print("=" * 70 + "\n")
        sys.exit(1)


@pytest.fixture(scope="session")
def anyio_backend():
    """Override anyio backend to only use asyncio (not trio)."""
    return "asyncio"


@pytest.fixture(scope="session")
def bootstrap_uv_env(tmp_path_factory):
    """Env for running scripts/bootstrap_skill.sh (its `uv sync` / `uv run`).

    Without this, `uv sync` re-syncs the project's own .venv -- usually the very
    interpreter running pytest -- to the lockfile's default set, uninstalling
    packages (mcp, mammoth, ...) mid-session so later tests silently skip.
    UV_FROZEN keeps it from rewriting the tracked uv.lock as well.
    """
    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = str(tmp_path_factory.mktemp("bootstrap-uv-env") / ".venv")
    env["UV_FROZEN"] = "1"
    env.pop("VIRTUAL_ENV", None)
    return env
