"""
Pytest configuration for tests.

Configures anyio to only use asyncio backend (not trio).
Checks that the skill_seekers package is installed before running tests.
"""

import os
import sys

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
