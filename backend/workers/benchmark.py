"""Measures how much traffic this box can actually score.

The number that decides whether a deployment is viable. A quiet ICU VLAN might
produce a few flows per second; a busy one with imaging and a chatty HIS produces
hundreds. If the pipeline is slower than the traffic, the backlog grows without
bound and the detection that mattered arrives after the shift ended — so this has
to be measured on the actual hardware, not assumed.

Reports two things separately, because they fail for different reasons:

  * inference — the models. Fixed cost per flow, fixed by the hardware.
  * end-to-end — models plus the database writes. This is where a slow disk or a
    contended MySQL shows up, and it is usually the larger half.

    cd backend && ./venv/Scripts/python.exe -m workers.benchmark --flows 200
    cd backend && ./venv/Scripts/python.exe -m workers.benchmark --inference-only
"""

import argparse
import statistics
import sys
import time
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text  # noqa: E402

from database import SessionLocal  # noqa: E402
from models.device import Device  # noqa: E402
from models.ml_model import MlModel  # noqa: E402
from services import detection_service, inference_service  # noqa: E402
from workers import replay  # noqa: E402


def _percentiles(samples: list[float]) -> dict:
    ordered = sorted(samples)
    def at(p): return ordered[min(int(len(ordered) * p), len(ordered) - 1)]
    return {
        "mean_ms": statistics.fmean(ordered),
        "median_ms": statistics.median(ordered),
        "p95_ms": at(0.95),
        "p99_ms": at(0.99),
        "max_ms": ordered[-1],
    }


def _report(label: str, samples: list[float]) -> None:
    stats = _percentiles(samples)
    print(f"\n{label}")
    print(f"  mean   {stats['mean_ms']:>8.2f} ms      -> {1000 / stats['mean_ms']:>7.1f} flows/sec")
    print(f"  median {stats['median_ms']:>8.2f} ms")
    print(f"  p95    {stats['p95_ms']:>8.2f} ms")
    print(f"  p99    {stats['p99_ms']:>8.2f} ms      <- size the deployment on this, not the mean")
    print(f"  max    {stats['max_ms']:>8.2f} ms")


def bench_inference(vectors, models: dict, rounds: int) -> list[float]:
    samples = []
    for i in range(rounds):
        vector = vectors[i % len(vectors)]
        start = time.perf_counter()
        inference_service.run_stage1(feature_vector=vector, **models["stage1"])
        if models.get("stage3"):
            inference_service.run_stage3(feature_vector=vector, **models["stage3"])
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--flows", type=int, default=100, help="how many flows to score")
    parser.add_argument("--inference-only", action="store_true",
                        help="skip the database writes and measure the models alone")
    args = parser.parse_args()

    print("Loading feature vectors from the capture...")
    _, features, _ = replay.load_frames()
    vectors = [features.iloc[i].tolist() for i in range(min(args.flows, len(features)))]

    db = SessionLocal()
    try:
        stage1 = db.query(MlModel).filter(MlModel.stage == 1, MlModel.is_active.is_(True)).first()
        stage3 = db.query(MlModel).filter(MlModel.stage == 3, MlModel.is_active.is_(True)).first()
        if stage1 is None:
            raise SystemExit("no active Stage 1 model — nothing to measure")

        models = {
            "stage1": {"artifact_path": stage1.artifact_path, "scaler_path": stage1.scaler_path},
            "stage3": ({"artifact_path": stage3.artifact_path, "scaler_path": stage3.scaler_path,
                        "threshold": float(stage3.threshold)} if stage3 and stage3.threshold else None),
        }

        # The first call of each model pays for loading the artifact and building
        # the compiled graph. Including that in the numbers would understate the
        # steady-state throughput by an order of magnitude.
        print("Warming up the model caches...")
        bench_inference(vectors, models, min(5, len(vectors)))

        print(f"\nScoring {len(vectors)} flows...")
        _report("Inference only (Stage 1 + Stage 3)",
                bench_inference(vectors, models, len(vectors)))

        if args.inference_only:
            return

        device = db.query(Device).order_by(Device.id).first()
        if device is None:
            raise SystemExit("no devices registered — nothing to attribute detections to")

        before = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM detections")).scalar()
        samples = []
        for vector in vectors:
            start = time.perf_counter()
            detection_service.submit_detection(
                db, flow_uid=None, device_id=device.id, feature_vector=vector,
                feature_set_version="v1", src_ip="10.0.0.1", dst_ip="10.0.0.2",
                protocol="TCP", capture_source="simulated",
            )
            samples.append((time.perf_counter() - start) * 1000)
        _report("End to end (models + database writes)", samples)

        # The benchmark's own rows are not evidence of anything; leaving them
        # would pollute every report generated afterwards. Children first —
        # alerts reference detections, so detections cannot go until they do.
        alert_ids = [r[0] for r in db.execute(
            text("SELECT id FROM alerts WHERE detection_id > :n"), {"n": before})]
        if alert_ids:
            for table in ("notifications", "alert_actions",
                          "mitigation_recommendations", "blocklist"):
                db.execute(text(f"DELETE FROM {table} WHERE alert_id IN :ids"),
                           {"ids": tuple(alert_ids)})
            db.execute(text("DELETE FROM alerts WHERE id IN :ids"), {"ids": tuple(alert_ids)})
        for statement in (
            "DELETE FROM flow_features WHERE flow_id > :n",
            "DELETE FROM detections WHERE id > :n",
            "DELETE FROM network_flows WHERE id > :n",
        ):
            db.execute(text(statement), {"n": before})
        db.commit()
        raised = f" and {len(alert_ids)} alerts they raised" if alert_ids else ""
        print(f"\n  removed the {len(samples)} benchmark detections{raised}")

        sustained = 1000 / _percentiles(samples)["p99_ms"]
        print(f"\nSustainable at p99: ~{sustained:.0f} flows/sec on this hardware.")
        print("Compare that against the ward's actual flow rate before deploying. A VLAN that")
        print("produces more than this needs a bigger box, or one box per ward.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
