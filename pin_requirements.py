"""Write requirements.txt / requirements-dev.txt with exact installed versions.

Edit requirements.in (app packages) or requirements-dev.in (tools), install them in
your venv, then run from the project root:
    python -m scripts.pin_requirements
"""
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_names(path):
    """Read package names from a .in file, ignoring comments and blank lines."""
    lines = [line.split("#")[0].strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line]


def pin(names):
    """Return (name==version list, names that are not installed)."""
    pinned, missing = [], []
    for name in names:
        try:
            pinned.append(f"{name}=={metadata.version(name)}")
        except metadata.PackageNotFoundError:
            missing.append(name)
    return pinned, missing


def main():
    """Write the pinned requirements files; returns a non-zero exit code if anything is missing."""
    problems = []
    for source, target, header in [
        ("requirements.in", "requirements.txt", []),
        ("requirements-dev.in", "requirements-dev.txt", ["-r requirements.txt"]),
    ]:
        path = ROOT / source
        if not path.exists():
            print(f"skipped {source} (not found)")
            continue
        pinned, missing = pin(read_names(path))
        (ROOT / target).write_text("\n".join(header + pinned) + "\n", encoding="utf-8")
        print(f"wrote {target}: {len(pinned)} packages")
        problems += missing
    if problems:
        print("NOT INSTALLED (pip install them, then rerun):", ", ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
