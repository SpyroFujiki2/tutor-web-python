"""Cross-platform setup: python scripts/setup.py [--docker] [--db-port 5433]."""

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", action="store_true", help="Start PostgreSQL with Docker Compose")
    parser.add_argument("--db-port", type=int)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Use Python 3.14, the supported/tested version for this project.")
    if args.db_port is not None and not 1 <= args.db_port <= 65535:
        parser.error("--db-port must be between 1 and 65535")
    if args.docker and shutil.which("docker") is None:
        raise SystemExit("Install/start Docker with Compose support, or use an installed PostgreSQL server.")
    env_dir = ROOT / "backend" / ".venv"
    python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(env_dir)

    def run(*command: str, env: dict[str, str] | None = None) -> None:
        subprocess.run(command, cwd=ROOT, check=True, env=env)

    try:
        run(str(python), "-m", "pip", "install", "-r", "backend/requirements-dev.txt")
        init_args = ["--docker"] if args.docker else []
        if args.db_port is not None:
            init_args.extend(["--db-port", str(args.db_port)])
        run(str(python), "backend/scripts/init_env.py", *init_args)
        if args.docker:
            # Derive the published port from the SAME URL as the backend.
            port = subprocess.check_output(
                [str(python), "-c", "from app.core.config import get_database_settings; print(get_database_settings().url.port or 5432)"],
                cwd=ROOT / "backend", text=True,
            ).strip()
            run("docker", "compose", "up", "-d", "--wait", "postgres", env={**os.environ, "POSTGRES_PORT": port})
        # Native PostgreSQL prompts only when the project database needs creating.
        run(str(python), "backend/scripts/bootstrap_db.py", *(["--docker"] if args.docker else []))
        run(str(python), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head")
        run(str(python), "backend/scripts/check_db.py")
    except subprocess.CalledProcessError:
        raise SystemExit("Setup stopped at the failed step. Correct its configuration and rerun; existing secrets are preserved.") from None
    print("Setup completed. Run the backend using the commands in README.md.")


if __name__ == "__main__":
    main()
