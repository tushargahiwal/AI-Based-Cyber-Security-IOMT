"""Drives the detection pipeline from the UI, for demonstrations and testing.

This is the Attack Simulator behind `POST /api/v1/simulate`. It replays real
rows from the labelled capture through the ordinary pipeline — the same call
`workers/replay.py` makes — so what appears on the live monitor is a genuine
model verdict on genuine attack traffic, not a scripted animation.

The run happens on its own thread with its own session, because a simulation is
paced (rows per second) and would otherwise hold a request worker for its whole
duration. One run at a time: two concurrent simulations writing interleaved
vitals for the same device would corrupt each other's Stage 4 windows.
"""

import threading
from datetime import datetime, timedelta

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from database import SessionLocal
from models.device import Device
from services import detection_service, inference_service, vitals_service
from workers import replay

# Enough rows for Stage 4 to have a full 31-reading window partway through a
# default-length run, so a simulation can actually exercise all four stages.
MAX_ROWS = 500

_lock = threading.Lock()
_state: dict = {"status": "idle", "started_at": None, "processed": 0, "total": 0,
                "mode": None, "device_uid": None, "verdicts": {}, "alerts": 0, "error": None}
_stop = threading.Event()
_thread: threading.Thread | None = None


def _select_indices(raw, mode: str, rows: int) -> list[int]:
    """Row indices to replay, kept contiguous so the vitals series stays real.

    'attack' and 'benign' walk to the largest run of that label rather than
    picking scattered rows: Stage 4 forecasts from the previous 30 readings, and
    a stitched-together sequence would make every reading look implausible.
    """
    labels = raw["Label"].to_numpy()
    if mode == "mixed":
        # Start shortly before the first substantial attack run so the operator
        # sees the transition from quiet traffic to an attack, not just the attack.
        boundaries = np.flatnonzero((labels[1:] == 1) & (labels[:-1] == 0)) + 1
        if len(boundaries) == 0:
            return list(range(min(rows, len(labels))))
        pivot = int(boundaries[0])
        start = max(0, pivot - rows // 3)
        return list(range(start, min(start + rows, len(labels))))

    wanted = 1 if mode == "attack" else 0
    best_start, best_len, run_start = 0, 0, 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[i - 1]:
            if labels[i - 1] == wanted and (i - run_start) > best_len:
                best_start, best_len = run_start, i - run_start
            run_start = i
    if best_len == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"the capture has no '{mode}' rows")
    return list(range(best_start, best_start + min(rows, best_len)))


def _run(indices: list[int], device_id: int, speed: float) -> None:
    db: Session = SessionLocal()
    try:
        raw, features, vitals = replay.load_frames()
        vital_names = inference_service.get_vitals_order()
        interval = 1.0 / speed if speed > 0 else 0.0
        clock = datetime.utcnow() - timedelta(seconds=len(indices))

        for n, idx in enumerate(indices):
            if _stop.is_set():
                _state["status"] = "stopped"
                return

            v = vitals.loc[idx]
            vitals_service.ingest_reading(db, data={
                "device_id": device_id,
                "recorded_at": clock + timedelta(seconds=n),
                "heart_rate": int(v["Heart_rate"]),
                "spo2": int(v["SpO2"]),
                "systolic_bp": int(v["SYS"]),
                "diastolic_bp": int(v["DIA"]),
                "body_temp": round(float(v["Temp"]), 2),
                "respiration_rate": int(v["Resp_Rate"]),
                "raw_payload": {name: float(v[name]) for name in vital_names},
            })
            result = detection_service.submit_detection(
                db,
                flow_uid=None,
                device_id=device_id,
                feature_vector=features.loc[idx].tolist(),
                feature_set_version="v1",
                src_ip=replay.SRC_IP,
                dst_ip=replay.DST_IP,
                protocol="TCP",
                capture_source="simulated",
            )
            verdict = result["detection"].final_verdict
            _state["verdicts"][verdict] = _state["verdicts"].get(verdict, 0) + 1
            if result["alert"] is not None:
                _state["alerts"] += 1
            _state["processed"] = n + 1

            if interval:
                _stop.wait(interval)

        _state["status"] = "completed"
    except Exception as exc:  # a failed simulation must not take the server with it
        _state["status"] = "failed"
        _state["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        _state["finished_at"] = datetime.utcnow()
        db.close()


def start(db: Session, *, mode: str, rows: int, speed: float, device_id: int | None) -> dict:
    global _thread

    with _lock:
        if _state["status"] == "running":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"a simulation is already running ({_state['processed']}/{_state['total']} rows)",
            )

        if device_id is None:
            device = (
                db.query(Device)
                .filter(Device.device_type.has(is_life_critical=True), Device.status != "quarantined")
                .order_by(Device.id)
                .first()
            )
            if device is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "no available life-critical device to simulate on")
        else:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown device_id {device_id}")

        raw, _, _ = replay.load_frames()
        indices = _select_indices(raw, mode, min(rows, MAX_ROWS))

        _stop.clear()
        _state.update({
            "status": "running", "started_at": datetime.utcnow(), "finished_at": None,
            "processed": 0, "total": len(indices), "mode": mode,
            "device_uid": device.device_uid, "verdicts": {}, "alerts": 0, "error": None,
        })
        _thread = threading.Thread(
            target=_run, args=(indices, device.id, speed), name="attack-simulator", daemon=True
        )
        _thread.start()

    return dict(_state)


def stop() -> dict:
    if _state["status"] != "running":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no simulation is running")
    _stop.set()
    return dict(_state)


def get_status() -> dict:
    return dict(_state)
