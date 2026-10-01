#!/usr/bin/env python3
"""Manage one repo-owned Hermes external skill directory registration."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

# Prefer ruamel.yaml's round-trip mode so we don't clobber comments/formatting
# in a config file we don't own. Fall back to PyYAML (safe_load/safe_dump)
# when ruamel isn't importable — the interpreter probe in install.sh only
# guarantees `import yaml`, not ruamel.
try:
    from ruamel.yaml import YAML

    _yaml = YAML()
    _yaml.preserve_quotes = True
except ImportError:
    _yaml = None
    import yaml


def normalize(path: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(path))
    return str(Path(expanded).resolve())


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        if _yaml is not None:
            data = _yaml.load(handle) or {}
        else:
            data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"error: Hermes config is not a YAML mapping: {path}")
    return data


def write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if _yaml is not None:
                _yaml.dump(data, handle)
            else:
                yaml.safe_dump(data, handle, sort_keys=False, default_flow_style=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def update(path: Path, external_dir: str, action: str) -> bool:
    data = load_config(path)
    skills = data.setdefault("skills", {})
    if not isinstance(skills, dict):
        raise SystemExit(f"error: Hermes 'skills' config is not a mapping: {path}")

    raw_dirs = skills.get("external_dirs", [])
    if isinstance(raw_dirs, str):
        dirs = [raw_dirs]
    elif isinstance(raw_dirs, list):
        # Mutate the loaded list in place rather than rebuilding a plain one:
        # in ruamel round-trip mode, a fresh list drops the per-node comment
        # and indent metadata the original CommentedSeq carries.
        dirs = raw_dirs
    elif raw_dirs is None:
        dirs = []
    else:
        raise SystemExit(
            f"error: Hermes skills.external_dirs must be a string or list: {path}"
        )

    target = normalize(external_dir)
    indices = [i for i, value in enumerate(dirs) if normalize(str(value)) == target]

    if action == "install":
        if not indices:
            dirs.append(target)
            skills["external_dirs"] = dirs
            write_config(path, data)
            return True
        return False

    if action == "uninstall":
        if not indices:
            return False
        for i in reversed(indices):
            del dirs[i]
        skills["external_dirs"] = dirs
        write_config(path, data)
        return True

    raise SystemExit(f"error: unsupported action: {action}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--external-dir", required=True)
    parser.add_argument("--action", choices=("install", "uninstall"), required=True)
    args = parser.parse_args()

    changed = update(args.config, args.external_dir, args.action)
    verb = "Registered" if args.action == "install" else "Unregistered"
    status = "" if changed else " (already up to date)"
    print(f"  {verb} Hermes external skills directory: {normalize(args.external_dir)}{status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
