"""重新打包 exe。用法：py -3 build_exe.py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        print("缺少 .venv，请先执行：py -3 -m venv .venv")
        return 1
    return subprocess.run(
        [
            str(python), "-m", "PyInstaller",
            "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", "视频随机编号",
            "--distpath", str(ROOT / "dist"),
            "--workpath", str(ROOT / "build"),
            "--specpath", str(ROOT / "build"),
            str(ROOT / "src" / "app.py"),
        ],
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
