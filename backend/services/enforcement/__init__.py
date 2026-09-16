"""Actuator registry, loaded from system_config.

Every actuator is off and in dry run until someone deliberately turns it on, per
actuator, in the database. There is no code path that enables enforcement as a
side effect of anything else.

Config keys, all under system_config:

    enforcement.enabled              global kill switch — "false" stops everything
    enforcement.arp_heal.enabled     per-actuator live/dry-run
    enforcement.arp_heal.config      JSON, e.g. {"interface": "eth0"}
    enforcement.switch_port.enabled
    enforcement.switch_port.config   {"template": "ssh sw1 ...", "label": "core-sw"}
    enforcement.firewall.enabled
    enforcement.firewall.config
    enforcement.mqtt_revoke.enabled
    enforcement.mqtt_revoke.config   {"host": "10.0.0.5", "username": "admin"}
"""

import json
import logging

from sqlalchemy.orm import Session

from models.system_config import SystemConfig

from .arp_heal import ArpHealActuator
from .base import Actuator, EnforcementResult
from .command import CommandActuator, FirewallActuator, SwitchPortActuator
from .mqtt_broker import MqttRevokeActuator

logger = logging.getLogger(__name__)

ACTUATOR_TYPES: dict[str, type[Actuator]] = {
    ArpHealActuator.name: ArpHealActuator,
    SwitchPortActuator.name: SwitchPortActuator,
    FirewallActuator.name: FirewallActuator,
    MqttRevokeActuator.name: MqttRevokeActuator,
}

KILL_SWITCH_KEY = "enforcement.enabled"


def _config_value(db: Session, key: str) -> str | None:
    row = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    return row.config_value if row else None


def _truthy(value: str | None) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def enforcement_enabled(db: Session) -> bool:
    """The global kill switch. Absent means off — enforcement is opt-in."""
    return _truthy(_config_value(db, KILL_SWITCH_KEY))


def load(db: Session, name: str) -> Actuator | None:
    """Builds one actuator from config, or None if the type is unknown."""
    actuator_type = ACTUATOR_TYPES.get(name)
    if actuator_type is None:
        return None

    raw = _config_value(db, f"enforcement.{name}.config")
    try:
        config = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        # Malformed config must not silently become an empty one that then looks
        # merely "unconfigured" — that would hide a typo behind a plausible state.
        logger.warning("enforcement.%s.config is not valid JSON — treating as unconfigured", name)
        config = {}

    # Live only when BOTH the global switch and this actuator's own flag are on.
    live = enforcement_enabled(db) and _truthy(_config_value(db, f"enforcement.{name}.enabled"))
    return actuator_type(config, dry_run=not live)


def load_all(db: Session) -> dict[str, Actuator]:
    return {name: load(db, name) for name in ACTUATOR_TYPES}


def status(db: Session) -> dict:
    """What is configured, what is live, and what is only pretending."""
    global_on = enforcement_enabled(db)
    actuators = []
    for name, actuator in load_all(db).items():
        ready, why = actuator.available()
        actuators.append({
            "name": name,
            "configured": ready,
            "detail": why,
            "dry_run": actuator.dry_run,
            "live": ready and not actuator.dry_run,
        })
    return {
        "enforcement_enabled": global_on,
        "actuators": actuators,
        "live_count": sum(1 for a in actuators if a["live"]),
    }


__all__ = [
    "Actuator", "EnforcementResult", "ACTUATOR_TYPES", "KILL_SWITCH_KEY",
    "enforcement_enabled", "load", "load_all", "status",
    "ArpHealActuator", "CommandActuator", "SwitchPortActuator",
    "FirewallActuator", "MqttRevokeActuator",
]
