"""Stage 4 physiological plausibility on the vitals stream (doc §8.7).

Stages 1-3 score one network flow in isolation; Stage 4 cannot — the LSTM needs
the previous WINDOW readings from the SAME device. So the work happens here at
ingest time (where the history is available) and detection_service only reads
the verdict back off the most recent reading.
"""

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.device import Device
from models.ml_model import MlModel
from models.vital_reading import VitalReading
from services import inference_service

# vitals_lstm_results.json names vitals as the WUSTL CSV does; these are the
# vital_readings columns holding the same six, in that same order.
VITAL_COLUMNS = {
    "Heart_rate": "heart_rate",
    "SpO2": "spo2",
    "SYS": "systolic_bp",
    "DIA": "diastolic_bp",
    "Temp": "body_temp",
    "Resp_Rate": "respiration_rate",
}

# A detection only counts a Stage 4 flag as corroborating evidence if the reading
# that raised it is recent — an injection flagged an hour ago says nothing about
# the flow being scored now.
STAGE4_CORRELATION_WINDOW = timedelta(minutes=5)

DEFAULT_ZSCORE_THRESHOLD = 3.0


def _resolve_active_stage4_model(db: Session) -> MlModel | None:
    return db.query(MlModel).filter(MlModel.stage == 4, MlModel.is_active.is_(True)).first()


def _row_to_vector(reading: VitalReading) -> list[float] | None:
    """Vitals in the model's expected order, or None if any is missing."""
    values = []
    for name in inference_service.get_vitals_order():
        value = getattr(reading, VITAL_COLUMNS[name])
        if value is None:
            return None
        values.append(float(value))
    return values


def _recent_readings(db: Session, device_id: int, limit: int) -> list[VitalReading]:
    """The last `limit` readings for a device, oldest first."""
    rows = (
        db.query(VitalReading)
        .filter(VitalReading.device_id == device_id)
        .order_by(VitalReading.recorded_at.desc(), VitalReading.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def _score_stage4(db: Session, reading: VitalReading) -> None:
    """Fills reading's Stage 4 columns in place. Silently no-ops when Stage 4
    can't run (no active model, not enough history, a gap in the vitals)."""
    model = _resolve_active_stage4_model(db)
    if model is None:
        return

    window_size = inference_service.get_vitals_window()
    history = _recent_readings(db, reading.device_id, window_size + 1)
    if len(history) < window_size + 1:
        return  # device is still filling its first window

    vectors = [_row_to_vector(r) for r in history]
    if any(v is None for v in vectors):
        return  # a sensor dropout in the window — no reliable forecast to compare against

    threshold = float(model.threshold) if model.threshold is not None else DEFAULT_ZSCORE_THRESHOLD
    result = inference_service.run_stage4(
        artifact_path=model.artifact_path,
        scaler_path=model.scaler_path,
        window=vectors,
        threshold=threshold,
    )

    reading.predicted_values = {
        "predicted": result["predicted_values"],
        "zscores": result["zscores"],
        "worst_vital": result["worst_vital"],
        "threshold": threshold,
    }
    # residual_zscore is DECIMAL(6,3); a near-zero residual_std can produce a
    # much larger z than that column holds, and the exact magnitude past this
    # point carries no extra meaning.
    reading.residual_zscore = min(result["max_zscore"], 999.999)
    reading.injection_suspected = result["injection_suspected"]
    reading.is_plausible = not result["injection_suspected"]


def ingest_reading(db: Session, *, data: dict) -> VitalReading:
    device = db.query(Device).filter(Device.id == data["device_id"]).first()
    if device is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown device_id {data['device_id']}")

    payload = dict(data)
    payload.setdefault("recorded_at", datetime.utcnow())
    reading = VitalReading(**payload)
    db.add(reading)
    db.flush()  # so this reading is the window's last row when history is queried

    _score_stage4(db, reading)

    db.commit()
    db.refresh(reading)
    return reading


def get_stage4_status(db: Session, device_id: int | None, *, at: datetime | None = None) -> VitalReading | None:
    """Latest reading for a device, if it is recent enough to bear on a detection."""
    if device_id is None:
        return None
    reading = (
        db.query(VitalReading)
        .filter(VitalReading.device_id == device_id)
        .order_by(VitalReading.recorded_at.desc(), VitalReading.id.desc())
        .first()
    )
    if reading is None or reading.residual_zscore is None:
        return None
    if (at or datetime.utcnow()) - reading.recorded_at > STAGE4_CORRELATION_WINDOW:
        return None
    return reading


def list_readings(db: Session, *, page: int, size: int, device_id: int | None = None,
                  patient_id: int | None = None, injection_only: bool = False):
    query = db.query(VitalReading)
    if device_id is not None:
        query = query.filter(VitalReading.device_id == device_id)
    if patient_id is not None:
        query = query.filter(VitalReading.patient_id == patient_id)
    if injection_only:
        query = query.filter(VitalReading.injection_suspected.is_(True))
    query = query.order_by(VitalReading.recorded_at.desc(), VitalReading.id.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


def get_reading(db: Session, reading_id: int) -> VitalReading | None:
    return db.query(VitalReading).filter(VitalReading.id == reading_id).first()
