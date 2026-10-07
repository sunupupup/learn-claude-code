"""一键构建 React 并启动 Python 服务，不需要同时管理两个常驻进程。"""

import argparse
import hashlib
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from threading import Timer
import webbrowser

from order_support_agent.config import load_settings
from order_support_agent.model import DeepSeekModel
from order_support_agent.server import AppServer


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="订单客服前后端一键启动")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    frontend = root / "frontend"
    try:
        settings = load_settings()
        # 在下载或构建前检查端口，不自动结束占用端口的其他进程。
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise ValueError("找不到 npm，请安装 Node.js 22.12+ 后重试。")
        local = root / ".local"
        local.mkdir(exist_ok=True)
        lock = frontend / "package-lock.json"
        install_marker = local / "frontend-dependencies.sha256"
        digest = hashlib.sha256(lock.read_bytes() if lock.exists() else (frontend / "package.json").read_bytes()).hexdigest()
        if not (frontend / "node_modules").is_dir() or not install_marker.exists() or install_marker.read_text() != digest:
            print("[1/3] 安装前端依赖（首次启动需要网络）…", flush=True)
            subprocess.run([npm, "ci" if lock.exists() else "install", "--no-audit", "--no-fund"], cwd=frontend, check=True)
            install_marker.write_text(hashlib.sha256(lock.read_bytes()).hexdigest())
        sources = [frontend / name for name in ("package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json")]
        sources += sorted((frontend / "src").rglob("*"))
        build_hash = hashlib.sha256(b"".join(p.read_bytes() for p in sources if p.is_file())).hexdigest()
        build_marker = local / "frontend-build.sha256"
        if not (frontend / "dist" / "index.html").exists() or not build_marker.exists() or build_marker.read_text() != build_hash:
            print("[2/3] 检查 TypeScript 并构建页面…", flush=True)
            subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
            build_marker.write_text(build_hash)
        server = AppServer(("127.0.0.1", args.port), DeepSeekModel(settings), settings)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        # 不打印配置对象或 .env 内容；启动失败保留用户已有文件。
        print(f"启动失败：{exc}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{args.port}"
    print(f"[3/3] 前后端已启动：{url}\n关闭本窗口或按 Ctrl+C 停止。", flush=True)
    if not args.no_open:
        Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
