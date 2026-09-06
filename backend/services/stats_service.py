from sqlalchemy import func
from sqlalchemy.orm import Session

from models.alert import Alert
from models.detection import Detection
from models.device import Device
from models.ml_model import MlModel
from models.network_flow import NetworkFlow


def get_overview(db: Session) -> dict:
    total_flows = db.query(func.count(NetworkFlow.id)).scalar()
    total_detections = db.query(func.count(Detection.id)).scalar()

    verdict_rows = (
        db.query(Detection.final_verdict, func.count(Detection.id))
        .group_by(Detection.final_verdict)
        .all()
    )
    detections_by_verdict = {verdict: count for verdict, count in verdict_rows}

    devices_total = db.query(func.count(Device.id)).scalar()
    devices_online = db.query(func.count(Device.id)).filter(Device.status == "online").scalar()

    active_model = (
        db.query(MlModel).filter(MlModel.stage == 1, MlModel.is_active.is_(True)).first()
    )

    active_alerts = (
        db.query(func.count(Alert.id)).filter(Alert.status.notin_(["resolved", "false_positive"])).scalar()
    )
    critical_alerts = (
        db.query(func.count(Alert.id))
        .filter(Alert.status.notin_(["resolved", "false_positive"]), Alert.severity == "critical")
        .scalar()
    )

    return {
        "total_flows": total_flows,
        "total_detections": total_detections,
        "detections_by_verdict": detections_by_verdict,
        "devices_online": devices_online,
        "devices_total": devices_total,
        "active_stage1_model": active_model.model_code if active_model else None,
        "active_alerts": active_alerts,
        "critical_alerts": critical_alerts,
    }
