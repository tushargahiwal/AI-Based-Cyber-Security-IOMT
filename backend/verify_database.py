"""Checks a database is actually ready before anything is pointed at it.

Run this after loading database/schema.sql into a fresh host — TiDB Cloud, a
managed MySQL, or a local one. It answers the questions that otherwise surface
much later and much more confusingly:

  * Did every table get created, or did the paste stop halfway?
  * Did the FOREIGN KEYs survive? Some hosts accept the syntax and silently
    create nothing, which means the constraints protecting the incident record
    from being orphaned are not there.
  * Are the ENUM columns the extended ones this code expects? The report type
    and alert action enums were widened after the first schema was written.

    cd backend && ./venv/Scripts/python.exe verify_database.py
    DATABASE_URL="mysql+pymysql://..." ./venv/Scripts/python.exe verify_database.py
"""

import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import settings

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "database" / "schema.sql"

# Values added to these enums after the original schema. If the host has the old
# definition, writes fail at runtime with a confusing LookupError rather than here.
EXPECTED_ENUM_VALUES = {
    ("reports", "report_type"): {"patient", "device", "ward"},
    ("alert_actions", "action"): {"reverted"},
}

# Columns added after the original schema.
EXPECTED_COLUMNS = {
    ("devices", "quarantined_until"),
    ("detections", "stage4_injection_suspected"),
    ("detections", "stage4_max_zscore"),
}


def expected_tables() -> list[str]:
    if not SCHEMA_PATH.exists():
        raise SystemExit(f"{SCHEMA_PATH} not found — run this from backend/")
    # IF NOT EXISTS is optional in the match: the schema uses it so a reload is
    # harmless, and without this the regex would name every table "IF".
    return re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+)",
                      SCHEMA_PATH.read_text(encoding="utf-8"))


def main() -> int:
    url = settings.database_url
    # Never print the password — this output gets pasted into chats and issues.
    safe = re.sub(r"://([^:]+):[^@]*@", r"://\1:***@", url)
    print(f"Connecting to {safe}\n")

    try:
        engine = create_engine(url, pool_pre_ping=True)
        connection = engine.connect()
    except SQLAlchemyError as exc:
        print(f"CANNOT CONNECT: {type(exc).__name__}")
        print(f"  {str(exc)[:300]}")
        print("\n  For TiDB Cloud, check the connection string keeps its TLS parameters:")
        print("    ?charset=utf8mb4&ssl_verify_cert=true&ssl_verify_identity=true")
        return 1

    problems = []
    with connection:
        version = str(connection.execute(text("SELECT VERSION()")).scalar())
        lowered = version.lower()
        flavour = ("TiDB" if "tidb" in lowered
                   else "MariaDB" if "mariadb" in lowered
                   else "MySQL")
        print(f"  server: {version}  ({flavour})")
        if flavour == "MariaDB":
            # Worth saying out loud: developing on MariaDB and deploying to TiDB
            # means the two ends differ in how JSON columns behave. JSON is a real
            # type on MySQL 8 / TiDB and a LONGTEXT alias on MariaDB, so a query
            # that compares an extracted JSON value can behave differently.
            print("    note: MariaDB treats JSON as a LONGTEXT alias. TiDB and MySQL 8 do not.")
            print("    Re-run this against the deployment target before trusting it.")
        database = connection.execute(text("SELECT DATABASE()")).scalar()
        print(f"  database: {database}\n")

        # --- tables ---
        present = {
            r[0] for r in connection.execute(text(
                "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"))
        }
        wanted = expected_tables()
        missing = [t for t in wanted if t not in present]
        print(f"  tables: {len(wanted) - len(missing)}/{len(wanted)} present")
        if missing:
            problems.append(f"{len(missing)} tables missing: {', '.join(missing[:6])}"
                            f"{' ...' if len(missing) > 6 else ''}")

        # --- foreign keys ---
        fk_count = connection.execute(text(
            "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_TYPE = 'FOREIGN KEY'"
        )).scalar() or 0
        expected_fks = SCHEMA_PATH.read_text(encoding="utf-8").count("FOREIGN KEY")
        print(f"  foreign keys: {fk_count}/{expected_fks}")
        if fk_count == 0 and expected_fks:
            problems.append(
                "no foreign keys exist. Some hosts accept the syntax and create nothing — "
                "without them an alert can outlive the detection it points at."
            )
        elif fk_count < expected_fks * 0.9:
            problems.append(f"only {fk_count} of {expected_fks} foreign keys were created")

        # --- columns added after the first schema ---
        for table, column in sorted(EXPECTED_COLUMNS):
            if table not in present:
                continue
            found = connection.execute(text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = :t AND COLUMN_NAME = :c"), {"t": table, "c": column}).scalar()
            if not found:
                problems.append(f"{table}.{column} is missing — this schema predates it")

        # --- widened enums ---
        for (table, column), values in EXPECTED_ENUM_VALUES.items():
            if table not in present:
                continue
            definition = connection.execute(text(
                "SELECT COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = :t AND COLUMN_NAME = :c"), {"t": table, "c": column}).scalar() or ""
            absent = [v for v in sorted(values) if f"'{v}'" not in definition]
            if absent:
                problems.append(
                    f"{table}.{column} is missing enum value(s) {', '.join(absent)} — "
                    f"reload database/schema.sql, it was widened after the first version"
                )

        # --- is there anything in it yet? ---
        if "users" in present:
            users = connection.execute(text("SELECT COUNT(*) FROM users")).scalar()
            models = connection.execute(text("SELECT COUNT(*) FROM ml_models")).scalar() \
                if "ml_models" in present else 0
            print(f"  rows: {users} users, {models} registered models")
            if users == 0:
                # Reference data now ships inside schema.sql, so the only thing
                # still missing is an account — and the first one to register
                # becomes an admin precisely because the table is empty.
                print("\n  No accounts yet. The first one to register is made an admin:")
                print("    open the app and use Register, or")
                print("    POST /api/v1/auth/register {username, email, password, role: 'admin'}")

    print()
    if problems:
        print(f"{len(problems)} PROBLEM(S):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Database looks correct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
