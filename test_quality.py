"""Project-wide quality gates: syntax, docstrings and secrets."""
import ast
import os
import py_compile
import re
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"venv", ".venv", "__pycache__", ".git", "data", "logs", "notebooks", ".ipynb_checkpoints"}
CODE_DIRS = ["api", "services", "models", "utils", "sql", "pages", "scripts"]


def project_files(suffixes, dirs=None):
    """Yield project files with the given suffixes, never entering virtual envs or data folders."""
    for base in ([ROOT / d for d in dirs] if dirs else [ROOT]):
        for folder, subdirs, files in os.walk(base):
            subdirs[:] = [d for d in subdirs
                          if d not in SKIP_DIRS and not (Path(folder) / d / "pyvenv.cfg").exists()]
            for name in files:
                if Path(name).suffix in suffixes:
                    yield Path(folder) / name


def python_files(dirs=None):
    """Yield the project's own .py files."""
    return project_files({".py"}, dirs)


@pytest.mark.parametrize("path", sorted(python_files()), ids=lambda p: str(p.relative_to(ROOT)))
def test_file_compiles(path):
    py_compile.compile(str(path), doraise=True)


@pytest.mark.parametrize("path", sorted(python_files(CODE_DIRS)), ids=lambda p: str(p.relative_to(ROOT)))
def test_modules_and_public_functions_have_docstrings(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if path.name != "__init__.py":
        assert ast.get_docstring(tree), f"{path.name}: missing module docstring"
    missing = [n.name for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.ClassDef))
               and not n.name.startswith("_")
               and not ast.get_docstring(n)]
    assert not missing, f"{path.name}: no docstring on {missing}"


def test_env_file_is_git_ignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for needed in (".env", "venv/", "logs/", "data/raw/", ".streamlit/secrets.toml"):
        assert needed in [line.strip() for line in gitignore], f"{needed} missing from .gitignore"


def test_env_example_has_no_real_key():
    example = ROOT / ".env.example"
    if example.exists():
        assert "your_key_here" in example.read_text(encoding="utf-8")


def test_api_key_is_not_written_in_any_project_file():
    key = getattr(config, "RAPIDAPI_KEY", None)
    if not key or len(str(key)) < 12:
        pytest.skip("no real API key configured")
    leaks = []
    scanned = list(project_files({".py", ".md", ".ipynb", ".txt", ".sql", ".json", ".toml"}))
    scanned += list(project_files({".ipynb"}, ["notebooks"]))      # notebooks, including cell outputs
    for path in scanned:
        if path.name != ".env" and str(key) in path.read_text(encoding="utf-8", errors="ignore"):
            leaks.append(str(path.relative_to(ROOT)))
    assert not leaks, f"API key found in: {leaks}"


# header name, then separators/quotes/backslashes (notebooks store code as escaped JSON),
# then a run of 20+ letters or digits = a real key, not os.getenv(...) or "your_key_here"
LEAK_PATTERN = re.compile(r"x-rapidapi-key[\\'\"\s:=]+[0-9a-zA-Z]{20,}", re.IGNORECASE)


FAKE_KEY = "AbCdEf0123456789aBcDeF0123456789AbCdEf0123456789xy"   # made up, not a real key


@pytest.mark.parametrize("text,leaks", [
    (f'headers = {{"x-rapidapi-key": "{FAKE_KEY}"}}', True),
    (f"headers = {{'x-rapidapi-key': '{FAKE_KEY}'}}", True),
    ('{"source": "headers = {\\\\"x-rapidapi-key\\\\": \\\\"' + FAKE_KEY + '\\\\"}"}', True),
    ('"x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),', False),
    ('"x-rapidapi-key": config.RAPIDAPI_KEY,', False),
    ('"x-rapidapi-key": "your_key_here"', False),
])
def test_leak_pattern_catches_real_keys_only(text, leaks):
    assert bool(LEAK_PATTERN.search(text)) is leaks


def test_no_hardcoded_key_in_notebooks():
    hits = [str(p.relative_to(ROOT)) for p in project_files({".ipynb"}, ["notebooks"])
            if LEAK_PATTERN.search(p.read_text(encoding="utf-8", errors="ignore"))] \
        if (ROOT / "notebooks").exists() else []
    assert not hits, f"Hard-coded API key in notebooks: {hits}"
