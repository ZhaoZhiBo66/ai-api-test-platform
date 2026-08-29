"""Bootstrap and run the platform together with its deterministic demo target."""

import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    environment = os.environ.copy()
    environment.setdefault("DATABASE_URL", f"sqlite:///{(ROOT_DIR / 'ai_test_platform.db').as_posix()}")
    environment.setdefault("ALLOW_PRIVATE_TARGETS", "true")
    environment.setdefault("TARGET_HOST_ALLOWLIST", "127.0.0.1,localhost")
    environment.setdefault("DEMO_SUT_URL", "http://127.0.0.1:8010")
    environment.setdefault("API_AUTH_ENABLED", "false")

    subprocess.run([sys.executable, "scripts/bootstrap_database.py"], cwd=ROOT_DIR, env=environment, check=True)
    subprocess.run([sys.executable, "scripts/seed_demo.py"], cwd=ROOT_DIR, env=environment, check=True)

    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "demo_sut.main:app", "--host", "127.0.0.1", "--port", "8010"],
            cwd=ROOT_DIR,
            env=environment,
        ),
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT_DIR,
            env=environment,
        ),
    ]
    print("Platform: http://127.0.0.1:8000/workbench")
    print("Demo API:  http://127.0.0.1:8010/docs")
    print("Press Ctrl+C to stop both services.")
    try:
        return processes[1].wait()
    except KeyboardInterrupt:
        return 0
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
