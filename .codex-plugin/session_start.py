"""Refresh crew scripts and roles when a Codex session starts in a crew project."""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    config_path = Path(".crew/config.json")
    if not config_path.is_file():
        return 0

    tools = Path(__file__).resolve().parents[1] / "tools"
    result = subprocess.run(
        [sys.executable, str(tools / "sync_bin.py"), "--project", ".", "--auto", "--json"],
        stdout=subprocess.PIPE, encoding="utf-8",
    )
    if result.returncode:
        return result.returncode
    if json.loads(result.stdout)["status"] != "ok":
        return 0

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not (Path(config.get("planDir", ".crew/plan")) / "models.json").is_file():
        return 0
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(tools / "render_roles.py"), "--project", "."],
        stdout=subprocess.PIPE, encoding="utf-8",
    )
    if result.stdout.strip() != "Roles are up to date.":
        sys.stdout.reconfigure(encoding="utf-8")
        print(result.stdout, end="")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
