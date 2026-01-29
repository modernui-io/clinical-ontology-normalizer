#!/usr/bin/env python3
import argparse
import os
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Install repo skills into CODEX_HOME.")
    parser.add_argument(
        "--source",
        default="skills",
        help="Source skills directory (default: skills/)",
    )
    parser.add_argument(
        "--codex-home",
        default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")),
        help="CODEX_HOME path (default: $CODEX_HOME or ~/.codex)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing skill directories",
    )
    args = parser.parse_args()

    src = Path(args.source).resolve()
    if not src.exists():
        raise SystemExit(f"Source skills dir not found: {src}")

    dest_root = Path(args.codex_home).expanduser().resolve() / "skills"
    dest_root.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if not item.is_dir():
            continue
        dest = dest_root / item.name
        if dest.exists():
            if not args.force:
                print(f"Skipping existing skill: {dest}")
                continue
            shutil.rmtree(dest)
        shutil.copytree(item, dest)
        print(f"Installed skill: {dest}")


if __name__ == "__main__":
    main()
