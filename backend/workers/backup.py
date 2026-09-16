"""Backs up and restores the database.

An IDS whose database is gone has lost the incident record — the alerts, who
acted on them and when. That is the part a NABH audit or an investigation asks
for, and it is not reconstructable from anywhere else. The models can be
retrained and the traffic is already past; the record cannot be recovered.

Uses mysqldump/mysql rather than a Python-side dump, because a restore has to
work from a machine that does not have this project on it — a plain .sql file
that any DBA can read and load is worth more in an incident than a clever format.

    cd backend && ./venv/Scripts/python.exe -m workers.backup create
    cd backend && ./venv/Scripts/python.exe -m workers.backup restore backups/iomt-20260906.sql
    cd backend && ./venv/Scripts/python.exe -m workers.backup verify backups/iomt-20260906.sql
"""

import argparse
import gzip
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from config import settings  # noqa: E402

BACKUP_DIR = _BACKEND_DIR.parent / "backups"

# Tables whose loss would be unrecoverable, as opposed to merely inconvenient.
# `verify` checks the dump actually contains them, because a backup that ran
# successfully and captured nothing is the worst kind.
CRITICAL_TABLES = ("alerts", "alert_actions", "audit_logs", "reports", "users", "devices")


def _connection() -> dict:
    """Pulls host/port/user/password/database out of the SQLAlchemy URL."""
    url = urlparse(settings.database_url.replace("mysql+pymysql://", "mysql://"))
    return {
        "host": url.hostname or "127.0.0.1",
        "port": str(url.port or 3306),
        "user": unquote(url.username or "root"),
        "password": unquote(url.password or ""),
        "database": (url.path or "/iomt_ids").lstrip("/").split("?")[0],
    }


# MySQL's client tools are routinely installed without being put on PATH,
# especially by XAMPP and MySQL Workbench on Windows. Looking in the usual
# places is the difference between backups working and nobody taking any.
_TOOL_SEARCH_GLOBS = [
    "C:/Program Files/MySQL/*/bin",
    "C:/Program Files/MySQL/MySQL Workbench*",
    "C:/xampp*/mysql/bin",
    "/usr/bin",
    "/usr/local/mysql/bin",
    "/opt/homebrew/bin",
]


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path

    import glob
    suffixes = (".exe", "") if sys.platform == "win32" else ("",)
    for pattern in _TOOL_SEARCH_GLOBS:
        for directory in glob.glob(pattern):
            for suffix in suffixes:
                candidate = Path(directory) / f"{name}{suffix}"
                if candidate.is_file():
                    return str(candidate)

    raise SystemExit(
        f"{name} was not found on PATH or in the usual install locations. It ships with the "
        f"MySQL client tools — install those or add MySQL's bin/ to PATH. This deliberately "
        f"does not reimplement them: a restore has to work from a machine that does not have "
        f"this project on it."
    )


def _base_args(conn: dict) -> list[str]:
    args = ["-h", conn["host"], "-P", conn["port"], "-u", conn["user"]]
    if conn["password"]:
        # Passed as one token so the password is not a separate argv entry that
        # shows up more readably in a process list. It is still visible to a
        # local `ps`; a production deployment should use a MySQL option file.
        args.append(f"-p{conn['password']}")
    return args


def create(*, compress: bool) -> Path:
    conn = _connection()
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"iomt-{stamp}.sql"

    print(f"Dumping {conn['database']} from {conn['host']}:{conn['port']} ...")
    command = [
        _tool("mysqldump"), *_base_args(conn),
        # single-transaction keeps the dump consistent without locking the
        # tables, so a backup does not stall live detections.
        "--single-transaction", "--routines", "--events",
        conn["database"],
    ]
    with open(target, "wb") as out:
        result = subprocess.run(command, stdout=out, stderr=subprocess.PIPE)
    if result.returncode != 0:
        target.unlink(missing_ok=True)
        raise SystemExit(f"mysqldump failed: {result.stderr.decode(errors='replace')[:400]}")

    if compress:
        gz = target.with_suffix(".sql.gz")
        with open(target, "rb") as raw, gzip.open(gz, "wb") as packed:
            shutil.copyfileobj(raw, packed)
        target.unlink()
        target = gz

    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"  {target.relative_to(_BACKEND_DIR.parent)}  ({size_mb:.1f} MB)")
    return target


def _read(path: Path) -> str:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        return f.read()


def verify(path: Path) -> bool:
    """Checks a dump is loadable-looking and contains what matters.

    A backup nobody has ever read back is a hope, not a backup.
    """
    if not path.exists():
        raise SystemExit(f"{path} does not exist")
    body = _read(path)
    missing = [t for t in CRITICAL_TABLES if f"CREATE TABLE `{t}`" not in body]
    inserts = body.count("INSERT INTO")

    print(f"{path.name}: {len(body) / 1024 / 1024:.1f} MB, {inserts} INSERT statements")
    if missing:
        print(f"  MISSING critical tables: {', '.join(missing)}")
        return False
    print(f"  all {len(CRITICAL_TABLES)} critical tables present")
    if inserts == 0:
        print("  ! schema only — no data. Fine for a fresh install, useless as a restore point.")
    return True


def restore(path: Path, *, yes: bool) -> None:
    conn = _connection()
    if not path.exists():
        raise SystemExit(f"{path} does not exist")

    print(f"About to restore {path.name} into {conn['database']} at {conn['host']}.")
    print("This OVERWRITES the current database, including any alerts raised since the backup.")
    if not yes:
        # An accidental restore destroys the incident record just as surely as a
        # disk failure does.
        answer = input(f"Type the database name ({conn['database']}) to confirm: ").strip()
        if answer != conn["database"]:
            raise SystemExit("not confirmed — nothing was changed")

    body = _read(path)
    result = subprocess.run(
        [_tool("mysql"), *_base_args(conn), conn["database"]],
        input=body.encode(), stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise SystemExit(f"restore failed: {result.stderr.decode(errors='replace')[:400]}")
    print("  restored. Restart the backend so it reconnects cleanly.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    make = sub.add_parser("create", help="write a new dump")
    make.add_argument("--no-compress", action="store_true", help="keep plain .sql")

    check = sub.add_parser("verify", help="check a dump contains what matters")
    check.add_argument("path")

    load = sub.add_parser("restore", help="load a dump, overwriting the current database")
    load.add_argument("path")
    load.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    args = parser.parse_args()
    if args.command == "create":
        path = create(compress=not args.no_compress)
        verify(path)
    elif args.command == "verify":
        raise SystemExit(0 if verify(Path(args.path)) else 1)
    else:
        restore(Path(args.path), yes=args.yes)


if __name__ == "__main__":
    main()
