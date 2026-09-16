"""Generates the reference/demo data section of database/schema.sql.

What ships and what does not is a deliberate choice, not a dump:

  SHIPPED  roles, wards, device_types, devices, patients, assignments,
           attack_types, datasets, ml_models, training_runs, model_metrics,
           feature_importances
           — reference data plus a demo estate. Reproducible, safe, and what a
             fresh install needs to be usable immediately.

  EXCLUDED users            password hashes must never sit in a committed file,
                            and the app bootstraps the first admin on its own
           user_sessions    live JWT records, meaningless anywhere else
           audit_logs       a record of who did what on one laptop; shipping it
                            would look like fabricated history
           detections,      development noise. The simulator regenerates these
           network_flows,   in seconds, and shipping them would put invented
           flow_features,   incidents into every report a new install produces
           alerts, ...
"""

import datetime
import decimal
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("backend").resolve()))

from sqlalchemy import text  # noqa: E402

from database import engine  # noqa: E402

# Order matters: a child table cannot be inserted before its parent exists.
TABLES = [
    ("roles", "reference"),
    ("wards", "reference"),
    ("device_types", "reference"),
    ("attack_types", "reference"),
    ("protocols", "reference"),
    ("datasets", "reference"),
    ("devices", "demo estate"),
    ("patients", "demo estate"),
    ("patient_device_assignments", "demo estate"),
    ("ml_models", "trained model registry"),
    ("training_runs", "trained model registry"),
    ("model_metrics", "trained model registry"),
    ("feature_importances", "trained model registry"),
    ("system_config", "reference"),
    ("thresholds", "reference"),
]

# Columns that point at a user. The users table is not shipped, so these are
# emitted as NULL rather than as a dangling id.
USER_REFERENCES = {"trained_by", "updated_by", "added_by", "generated_by", "applied_by", "user_id"}


def literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, decimal.Decimal):
        # str(Decimal) yields scientific notation ("0E-8") for values that came
        # back scaled. Valid SQL, but needlessly surprising in a file people read.
        return format(value.normalize(), "f")
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return "'" + value.isoformat(sep=" ") + "'"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, separators=(",", ":"))
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    # Doubling the quote is ANSI SQL and works whatever sql_mode the target runs.
    # A backslash escape is MySQL-specific and fails outright on a server with
    # NO_BACKSLASH_ESCAPES set — the kind of thing discovered halfway through
    # pasting into someone else's cloud console.
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def main() -> None:
    out = io.StringIO()
    out.write("\n")
    out.write("-- " + "=" * 74 + "\n")
    out.write("-- REFERENCE AND DEMO DATA\n")
    out.write("-- " + "=" * 74 + "\n")
    out.write("--\n")
    out.write("-- Everything below is data, not structure. A fresh install needs it to be\n")
    out.write("-- usable: the roles permissions are checked against, the ward and device-type\n")
    out.write("-- catalogues, a demo estate of 10 devices and 5 patients, and the registry of\n")
    out.write("-- trained models with the metrics the Models page reads.\n")
    out.write("--\n")
    out.write("-- Deliberately NOT included:\n")
    out.write("--   users         password hashes do not belong in a committed file. Register\n")
    out.write("--                 the first account through the API and it is made an admin,\n")
    out.write("--                 because it is the first — see services/auth_service.py.\n")
    out.write("--   detections,   development noise. The Attack Simulator regenerates these in\n")
    out.write("--   alerts,       seconds; shipping them would put invented incidents into\n")
    out.write("--   audit_logs    every report a new install produces.\n")
    out.write("--\n")
    out.write("-- Safe to re-run: every row is INSERT ... ON DUPLICATE KEY UPDATE id=id, which\n")
    out.write("-- leaves an existing row untouched rather than failing or overwriting it.\n")
    out.write("--\n")
    out.write("-- Regenerate after changing the reference data:\n")
    out.write("--   python scripts/generate_seed_sql.py\n")
    out.write("\n")

    with engine.connect() as connection:
        for table, group in TABLES:
            columns = [r[0] for r in connection.execute(text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t ORDER BY ORDINAL_POSITION"
            ), {"t": table})]
            if not columns:
                print(f"  {table:<30} table not found, skipped")
                continue

            rows = list(connection.execute(text(f"SELECT * FROM {table} ORDER BY id")))
            if not rows:
                print(f"  {table:<30} empty, skipped")
                continue

            out.write(f"-- {table} ({len(rows)} rows — {group})\n")
            column_list = ", ".join(f"`{c}`" for c in columns)
            values = []
            for row in rows:
                cells = []
                for name, value in zip(columns, row):
                    cells.append("NULL" if name in USER_REFERENCES else literal(value))
                values.append("  (" + ", ".join(cells) + ")")
            out.write(f"INSERT INTO `{table}` ({column_list}) VALUES\n")
            out.write(",\n".join(values))
            # id=id is a no-op that turns a duplicate-key error into "leave it
            # alone", which is what re-running a seed should do.
            out.write("\nON DUPLICATE KEY UPDATE id=id;\n\n")
            print(f"  {table:<30} {len(rows)} rows")

    body = out.getvalue()
    schema = Path("database/schema.sql")
    text_now = io.open(schema, encoding="utf-8", newline="").read()

    marker = "-- REFERENCE AND DEMO DATA"
    if marker in text_now:
        text_now = text_now[:text_now.index("-- " + "=" * 74 + "\n" + marker)].rstrip() + "\n"
    else:
        text_now = text_now.rstrip() + "\n"

    # FK checks are re-enabled at the end of the DDL; the data goes before that
    # so parents and children can be inserted without ordering anxiety.
    tail = "\nSET FOREIGN_KEY_CHECKS = 1;\n"
    if text_now.rstrip().endswith("SET FOREIGN_KEY_CHECKS = 1;"):
        text_now = text_now.rstrip()[: -len("SET FOREIGN_KEY_CHECKS = 1;")].rstrip() + "\n"

    io.open(schema, "w", encoding="utf-8", newline="").write(text_now + body + tail)
    print(f"\nwritten into {schema}")


if __name__ == "__main__":
    main()
