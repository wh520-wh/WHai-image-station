"""
PyInstaller 打包脚本
使用方式: python build.py
"""
import os
import sys
import subprocess

def build_exe():
    """打包为单个 exe 文件"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(project_root, "src")
    build_env = os.environ.copy()
    if os.name == "nt" and not build_env.get("USERPROFILE"):
        build_env["USERPROFILE"] = project_root

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=WHai-image-station",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        f"--add-data={src_dir};src",
        "--hidden-import=PySide6",
        "--hidden-import=httpx",
        "--hidden-import=PIL",
        "--hidden-import=cryptography",
        "--hidden-import=aiosqlite",
        "--exclude-module=setuptools",
        "--exclude-module=pkg_resources",
        "--exclude-module=pygame",
        "--exclude-module=yt_dlp",
        os.path.join(src_dir, "main.py"),
    ]

    print("开始打包...")
    print("命令:", " ".join(cmd))

    result = subprocess.run(cmd, cwd=project_root, env=build_env)
    if result.returncode == 0:
        print("打包成功！")
        print("输出目录: dist/WHai-image-station.exe")
    else:
        print("打包失败！")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
