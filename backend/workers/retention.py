"""Deletes telemetry that is past its retention window.

Two reasons, and the second is the one that matters more.

Operationally: detections, flows and vitals arrive continuously. A ward pushing
one reading per device per second fills a disk, and a full disk takes the whole
system down — including the detection that mattered. Something has to prune.

Legally: the vitals and the alerts are patient-linked. Under India's DPDP Act
2023 personal data is not to be kept longer than the purpose needs, and "we
never got round to deleting it" is not a purpose. Keeping a defined, enforced
window is the difference between a defensible position and an indefensible one.

What is NOT pruned here, deliberately:

  * alerts and alert_actions — the incident record. NABH and any investigation
    need these to outlive the raw telemetry they came from.
  * reports — a report is a frozen summary someone generated on purpose.
  * audit_logs — pruned, but on a much longer window, because they are the
    record of who did what and are what an audit asks for first.

Run from cron/Task Scheduler, or with --dry-run to see what would go:

    cd backend && ./venv/Scripts/python.exe -m workers.retention --dry-run
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

from config import settings  # noqa: E402
from database import SessionLocal  # noqa: E402

# Deleted in this order so a child row never outlives its parent. Each entry is
# (label, table, the SQL that selects what is too old).
PLAN = [
    ("flow_features", "detections",
     "DELETE ff FROM flow_features ff JOIN network_flows nf ON nf.id = ff.flow_id "
     "WHERE nf.flow_start < :cutoff"),
    ("detections", "detections",
     "DELETE FROM detections WHERE detected_at < :cutoff "
     # An alert points at its detection; deleting it out from under a live alert
     # would leave the console with a broken link.
     "AND id NOT IN (SELECT detection_id FROM alerts)"),
    ("network_flows", "detections",
     "DELETE FROM network_flows WHERE flow_start < :cutoff "
     "AND id NOT IN (SELECT flow_id FROM detections)"),
    ("vital_readings", "vitals",
     "DELETE FROM vital_readings WHERE recorded_at < :cutoff"),
    ("explanations", "detections",
     "DELETE FROM explanations WHERE detection_id NOT IN (SELECT id FROM detections)"),
    ("audit_logs", "audit",
     "DELETE FROM audit_logs WHERE created_at < :cutoff"),
]

WINDOWS = {
    "detections": settings.retention_detections_days,
    "vitals": settings.retention_vitals_days,
    "audit": settings.retention_audit_days,
}


def _count_sql(delete_sql: str) -> str:
    """Turns a DELETE into the SELECT COUNT that shows what it would remove."""
    if delete_sql.startswith("DELETE ff FROM"):
        return delete_sql.replace("DELETE ff FROM", "SELECT COUNT(*) FROM", 1)
    return delete_sql.replace("DELETE FROM", "SELECT COUNT(*) FROM", 1)


def run(*, dry_run: bool, now: datetime | None = None) -> dict:
    moment = now or datetime.utcnow()
    db = SessionLocal()
    removed: dict[str, int] = {}

    try:
        print(f"Retention windows: " + ", ".join(
            f"{k}={v}d" if v else f"{k}=disabled" for k, v in WINDOWS.items()))
        print(f"{'Would delete' if dry_run else 'Deleting'} rows older than these, as of "
              f"{moment:%Y-%m-%d %H:%M} UTC\n")

        for label, window_key, sql in PLAN:
            days = WINDOWS[window_key]
            if not days:
                print(f"  {label:<16} skipped ({window_key} retention disabled)")
                continue
            params = {"cutoff": moment - timedelta(days=days)}
            # The explanations sweep is a referential tidy-up with no date of
            # its own; it takes no cutoff parameter.
            if ":cutoff" not in sql:
                params = {}

            if dry_run:
                n = db.execute(text(_count_sql(sql)), params).scalar() or 0
            else:
                n = db.execute(text(sql), params).rowcount
            removed[label] = n
            print(f"  {label:<16} {n:>8} rows")

        if dry_run:
            db.rollback()
            print("\ndry run — nothing was deleted")
        else:
            db.commit()
            print(f"\ndeleted {sum(removed.values())} rows")
    finally:
        db.close()

    return {"checked_at": moment, "dry_run": dry_run, "removed": removed}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be deleted without deleting it")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
