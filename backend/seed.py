"""Idempotent reference-data seeder.

Run after the schema is created and on every fresh setup:
    cd backend && ./venv/Scripts/python.exe seed.py

Safe to re-run — existing rows are updated in place (matched by their
unique key), nothing is duplicated.
"""

import json

from sqlalchemy import text

from database import engine

ROLES = [
    {
        "name": "admin",
        "description": "Full system access — user management, model lifecycle, system configuration.",
        "permissions": [
            "alerts.read", "alerts.ack", "alerts.resolve", "alerts.assign", "alerts.comment",
            "devices.read", "devices.write", "devices.quarantine",
            "patients.read", "patients.write",
            "models.read", "models.retrain", "models.activate",
            "users.manage",
            "system_config.write",
            "vitals.read", "vitals.write",
            "reports.read", "reports.generate",
        ],
    },
    {
        "name": "security_analyst",
        "description": "IT Security — triages and resolves alerts, manages device response actions.",
        "permissions": [
            "alerts.read", "alerts.ack", "alerts.resolve", "alerts.assign", "alerts.comment",
            "devices.read", "devices.quarantine",
            "patients.read",
            "models.read",
            "vitals.read",
            "reports.read", "reports.generate",
        ],
    },
    {
        "name": "clinician",
        "description": "ICU / ward staff — views vitals and alerts for their patients' devices only.",
        "permissions": [
            "alerts.read",
            "devices.read",
            "patients.read", "patients.write",
            "vitals.read",
        ],
    },
    {
        "name": "viewer",
        "description": "Read-only access — dashboard, devices, alerts, reports. Cannot act on anything.",
        "permissions": [
            "alerts.read",
            "devices.read",
            "models.read",
            "vitals.read",
            "reports.read",
        ],
    },
]

UPSERT_ROLE_SQL = text(
    """
    INSERT INTO roles (name, description, permissions)
    VALUES (:name, :description, :permissions)
    ON DUPLICATE KEY UPDATE
        description = VALUES(description),
        permissions = VALUES(permissions)
    """
)


def seed_roles(conn):
    for role in ROLES:
        conn.execute(
            UPSERT_ROLE_SQL,
            {**role, "permissions": json.dumps(role["permissions"])},
        )
    print(f"Seeded {len(ROLES)} roles: {', '.join(r['name'] for r in ROLES)}")


# device_types.category: 'sensor' | 'actuator' | 'gateway' | 'hybrid' (doc §4.1 device list)
DEVICE_TYPES = [
    {"type_name": "Patient Monitor", "category": "sensor", "is_life_critical": True,
     "default_protocols": ["MQTT", "TCP"], "expected_data_rate_kbps": 12.0},
    {"type_name": "Infusion Pump", "category": "actuator", "is_life_critical": True,
     "default_protocols": ["MQTT"], "expected_data_rate_kbps": 4.0},
    {"type_name": "Ventilator", "category": "actuator", "is_life_critical": True,
     "default_protocols": ["MQTT", "TCP"], "expected_data_rate_kbps": 20.0},
    {"type_name": "Pulse Oximeter", "category": "sensor", "is_life_critical": False,
     "default_protocols": ["BLE", "MQTT"], "expected_data_rate_kbps": 2.0},
    {"type_name": "ECG Sensor", "category": "sensor", "is_life_critical": False,
     "default_protocols": ["BLE", "MQTT"], "expected_data_rate_kbps": 8.0},
    {"type_name": "Smart Bed", "category": "hybrid", "is_life_critical": False,
     "default_protocols": ["MQTT", "HTTP"], "expected_data_rate_kbps": 3.0},
    {"type_name": "Bedside Gateway", "category": "gateway", "is_life_critical": False,
     "default_protocols": ["MQTT", "TCP", "HTTP"], "expected_data_rate_kbps": 50.0},
]

UPSERT_DEVICE_TYPE_SQL = text(
    """
    INSERT INTO device_types (type_name, category, is_life_critical, default_protocols, expected_data_rate_kbps)
    VALUES (:type_name, :category, :is_life_critical, :default_protocols, :expected_data_rate_kbps)
    ON DUPLICATE KEY UPDATE
        category = VALUES(category),
        is_life_critical = VALUES(is_life_critical),
        default_protocols = VALUES(default_protocols),
        expected_data_rate_kbps = VALUES(expected_data_rate_kbps)
    """
)


def seed_device_types(conn):
    for dt in DEVICE_TYPES:
        conn.execute(
            UPSERT_DEVICE_TYPE_SQL,
            {**dt, "default_protocols": json.dumps(dt["default_protocols"])},
        )
    print(f"Seeded {len(DEVICE_TYPES)} device_types: {', '.join(d['type_name'] for d in DEVICE_TYPES)}")


WARDS = [
    {"name": "ICU-1", "floor": "3", "network_segment": "192.168.20.0/24", "criticality": "critical"},
    {"name": "ICU-2", "floor": "3", "network_segment": "192.168.21.0/24", "criticality": "critical"},
    {"name": "Emergency", "floor": "0", "network_segment": "192.168.10.0/24", "criticality": "high"},
    {"name": "General Ward A", "floor": "1", "network_segment": "192.168.30.0/24", "criticality": "medium"},
    {"name": "General Ward B", "floor": "2", "network_segment": "192.168.31.0/24", "criticality": "medium"},
]

UPSERT_WARD_SQL = text(
    """
    INSERT INTO wards (name, floor, network_segment, criticality)
    VALUES (:name, :floor, :network_segment, :criticality)
    ON DUPLICATE KEY UPDATE
        floor = VALUES(floor),
        network_segment = VALUES(network_segment),
        criticality = VALUES(criticality)
    """
)


def seed_wards(conn):
    # wards.name has no UNIQUE constraint in the schema, so upsert by matching name manually.
    for ward in WARDS:
        existing = conn.execute(
            text("SELECT id FROM wards WHERE name = :name"), {"name": ward["name"]}
        ).first()
        if existing:
            conn.execute(
                text(
                    "UPDATE wards SET floor=:floor, network_segment=:network_segment, "
                    "criticality=:criticality WHERE id=:id"
                ),
                {**ward, "id": existing.id},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO wards (name, floor, network_segment, criticality) "
                    "VALUES (:name, :floor, :network_segment, :criticality)"
                ),
                ward,
            )
    print(f"Seeded {len(WARDS)} wards: {', '.join(w['name'] for w in WARDS)}")


# Stage 4 is the only model this seeder registers: Stages 1-3 are registered
# through the Models UI as they are retrained, but Stage 4 has a fixed artifact
# and a threshold that comes from training (z > 3.0, see
# models/vitals_lstm_results.json) rather than from an operator's judgement.
STAGE4_MODEL = {
    "model_code": "VITALS_LSTM_V1",
    "display_name": "Vitals LSTM Forecaster (Stage 4)",
    "stage": 4,
    "algorithm": "LSTM",
    "task_type": "regression",
    "version": "v1",
    "artifact_path": "models/vitals_lstm_v1.keras",
    "scaler_path": "data/scalers/vitals_scaler_v1.pkl",
    "input_dim": 6,
    "threshold": 3.0,
    "is_active": True,
}

UPSERT_STAGE4_SQL = text(
    """
    INSERT INTO ml_models (model_code, display_name, stage, algorithm, task_type, version,
                           artifact_path, scaler_path, input_dim, threshold, is_active)
    VALUES (:model_code, :display_name, :stage, :algorithm, :task_type, :version,
            :artifact_path, :scaler_path, :input_dim, :threshold, :is_active)
    ON DUPLICATE KEY UPDATE
        display_name = VALUES(display_name),
        stage = VALUES(stage),
        algorithm = VALUES(algorithm),
        task_type = VALUES(task_type),
        artifact_path = VALUES(artifact_path),
        scaler_path = VALUES(scaler_path),
        input_dim = VALUES(input_dim),
        threshold = VALUES(threshold),
        is_active = VALUES(is_active)
    """
)


def seed_stage4_model(conn):
    conn.execute(UPSERT_STAGE4_SQL, STAGE4_MODEL)
    print(f"Seeded Stage 4 model: {STAGE4_MODEL['model_code']} (active, z-score threshold "
          f"{STAGE4_MODEL['threshold']})")


def main():
    with engine.begin() as conn:
        seed_roles(conn)
        seed_device_types(conn)
        seed_wards(conn)
        seed_stage4_model(conn)


if __name__ == "__main__":
    main()
