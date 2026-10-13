"""Build the portable Windows app using the single maintained spec."""

import os
import subprocess
import sys
from pathlib import Path


def build_exe():
    root = Path(__file__).resolve().parent
    environment = os.environ.copy()
    if os.name == "nt":
        # Prefer the interpreter and Windows DLLs over unrelated tools on PATH.
        system = Path(environment.get("SystemRoot", "C:/Windows")) / "System32"
        environment["PATH"] = os.pathsep.join(
            [str(Path(sys.executable).parent), str(Path(sys.base_prefix)), str(system), environment.get("PATH", "")]
        )
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "WHai-image-station.spec"],
        cwd=root,
        env=environment,
    )
    if result.returncode:
        raise SystemExit(result.returncode)
    name = "WHai-image-station-debug" if environment.get("WHAI_CONSOLE_BUILD") == "1" else "WHai-image-station"
    print(f"Ready: dist/{name}/{name}.exe")


if __name__ == "__main__":
    build_exe()
