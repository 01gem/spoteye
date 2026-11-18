"""Copy the license files of every runtime Python package bundled into the Spoteye build.

Usage (run with the build venv's Python):
    python -I packaging/collect_licenses.py backend/requirements.txt dist/Spoteye/licenses/python

Walks the dependency closure of requirements.txt (extras such as uvicorn[standard] included,
environment markers evaluated for this machine), so dev-only packages (pytest, pyinstaller) are
left out. Writes one folder per package plus THIRD_PARTY.md with name, version and license.
"""

from __future__ import annotations

import shutil
import sys
from importlib import metadata
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

LICENSE_HINTS = ("license", "licence", "copying", "notice", "authors")


def read_requirements(path: Path) -> list[Requirement]:
    reqs: list[Requirement] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        try:
            reqs.append(Requirement(line))
        except InvalidRequirement:
            print(f"warning: skipping unparsable requirement {line!r}", file=sys.stderr)
    return reqs


def closure(roots: list[Requirement]) -> dict[str, metadata.Distribution]:
    """Installed distributions reachable from roots, keyed by canonical name."""
    found: dict[str, metadata.Distribution] = {}
    queue: list[tuple[Requirement, frozenset[str]]] = [(r, frozenset(r.extras)) for r in roots]
    seen: set[tuple[str, frozenset[str]]] = set()
    while queue:
        req, extras = queue.pop()
        key = (canonicalize_name(req.name), extras)
        if key in seen:
            continue
        seen.add(key)
        try:
            dist = metadata.distribution(req.name)
        except metadata.PackageNotFoundError:
            print(f"warning: {req.name} is not installed", file=sys.stderr)
            continue
        found[key[0]] = dist
        for spec in dist.requires or []:
            child = Requirement(spec)
            envs = [{"extra": e} for e in extras] or [{"extra": ""}]
            if child.marker is None or any(child.marker.evaluate(env) for env in envs):
                queue.append((child, frozenset(child.extras)))
    return found


def license_name(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    for field in ("License-Expression", "License"):
        value = (meta.get(field) or "").strip()
        if value and len(value) < 120 and "\n" not in value:
            return value
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or []
                   if c.startswith("License ::")]  # fmt: skip
    return ", ".join(classifiers) or "see files"


def license_files(dist: metadata.Distribution) -> list[Path]:
    files: list[Path] = []
    for entry in dist.files or []:
        name = entry.name.lower()
        in_dist_info = any(part.endswith((".dist-info", ".egg-info")) for part in entry.parts[:-1])
        if in_dist_info and any(hint in name for hint in LICENSE_HINTS):
            path = Path(str(entry.locate()))
            if path.is_file():
                files.append(path)
    return files


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    requirements, dest = Path(argv[1]), Path(argv[2])
    dest.mkdir(parents=True, exist_ok=True)
    rows: list[str] = ["| Package | Version | License |", "|---|---|---|"]
    missing: list[str] = []
    for name, dist in sorted(closure(read_requirements(requirements)).items()):
        version = dist.version
        rows.append(f"| {dist.metadata['Name']} | {version} | {license_name(dist)} |")
        files = license_files(dist)
        if not files:
            missing.append(name)
            continue
        target = dest / f"{name}-{version}"
        target.mkdir(exist_ok=True)
        for file in files:
            shutil.copy2(file, target / file.name)
    summary = ["# Third-party Python packages bundled in Spoteye", "", *rows, ""]
    if missing:
        summary += ["No license file shipped in the package metadata for: " + ", ".join(missing),
                    "See each project's homepage on https://pypi.org for its license.", ""]  # fmt: skip
    (dest / "THIRD_PARTY.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"Collected licenses for {len(rows) - 2} packages into {dest}")
    if missing:
        print(f"note: no license file in metadata for {len(missing)}: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
