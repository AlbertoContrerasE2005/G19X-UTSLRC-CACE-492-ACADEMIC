"""Arranca DataOps Final: MySQL (externo), API Python :8010 y web PHP :8080."""

import argparse
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent


def need_port(port):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            print(f"Puerto {port} ocupado. Cierra la otra instancia.")
            return False
    return True


def wait_api(timeout=40):
    for _ in range(int(timeout * 4)):
        try:
            with urlopen("http://127.0.0.1:8010/api/health", timeout=0.5) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(0.25)
    return False


def main():
    arg = argparse.ArgumentParser(description="Iniciar DataOps Final")
    arg.add_argument("--no-browser", action="store_true")
    arg.add_argument("--python-only", action="store_true")
    args = arg.parse_args()

    missing = [
        m
        for m in ("fastapi", "uvicorn", "sklearn", "numpy", "pymysql", "openpyxl")
        if not importlib.util.find_spec(m)
    ]
    if missing:
        print("Faltan dependencias:", ", ".join(missing))
        print("Ejecuta: .venv\\Scripts\\python -m pip install -r requirements.txt")
        return 1

    # 1. Esquema MySQL (crea base y tablas si faltan).
    print("Preparando MySQL 127.0.0.1:3307 ...")
    from backend.db import init_schema

    try:
        init_schema()
    except Exception as exc:
        print(f"MySQL no responde: {exc}")
        print("Arranca MariaDB con tu mysql-data en el puerto 3307.")
        return 1

    php = (
        None
        if args.python_only
        else (os.environ.get("DATAOPS_PHP") or shutil.which("php"))
    )
    if not php and not args.python_only:
        for path in (r"C:\xampp\php\php.exe", r"C:\php\php.exe"):
            if Path(path).is_file():
                php = path
                break

    for port in ([8010] if not php else [8010, 8080]):
        if not need_port(port):
            return 1

    procs = []
    try:
        procs.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8010",
                    "--workers",
                    "1",
                ],
                cwd=ROOT,
            )
        )
        if not wait_api():
            print("Python no inició. Revisa la consola.")
            return 1
        if php:
            procs.append(
                subprocess.Popen(
                    [
                        php,
                        "-d",
                        "post_max_size=16M",
                        "-S",
                        "127.0.0.1:8080",
                        "-t",
                        str(ROOT / "web"),
                        str(ROOT / "php" / "router.php"),
                    ],
                    cwd=ROOT,
                )
            )
            url = "http://127.0.0.1:8080"
            time.sleep(0.4)
        else:
            url = "http://127.0.0.1:8010"
        print(f"Abre {url} y crea tu cuenta inicial.")
        print("Ctrl+C detiene todo.")
        if not args.no_browser:
            webbrowser.open(url)
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        return 1
    except KeyboardInterrupt:
        print("\nCerrando DataOps...")
        return 0
    finally:
        for proc in reversed(procs):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
