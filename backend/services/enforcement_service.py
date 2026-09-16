"""Deciding what to enforce, and against whom.

The second question is the one that matters, and getting it wrong is how a
security tool hurts a patient.

Our own mitigation code used to quarantine the *device the alert was about*. For
a man-in-the-middle that is exactly backwards. The monitor is the victim: it is
doing nothing wrong, an attacker has inserted themselves beside it. Cutting the
monitor off does not stop the attacker, it removes the patient from the central
station, and it leaves the attacker still on the network. Three failures from one
click.

So the first thing this module does is work out who the adversary actually is:

    registered device  +  a MAC that is not its registered MAC
        -> the adversary is that unregistered host, not the device

    the device itself flooding or scanning
        -> the device is compromised, and it IS the target — but it is also
           possibly life-critical, so nothing is automatic

Everything else follows from that. Enforcement is aimed at the adversary,
medical devices stay on the network, and a life-critical device is never acted
on without a person saying so explicitly.
"""

import logging
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.alert import Alert
from models.detection import Detection
from models.device import Device
from models.network_flow import NetworkFlow
from services import enforcement

logger = logging.getLogger(__name__)


@dataclass
class Adversary:
    """Who to act against, and how sure we are."""

    ip: str | None
    mac: str | None = None
    #: Why we think this is the hostile party — shown to the analyst verbatim.
    rationale: str = ""
    #: True when the adversary IS a registered medical device (it is compromised,
    #: rather than being attacked). Changes everything about what is allowed.
    is_registered_device: bool = False
    device: Device | None = None
    life_critical: bool = False


@dataclass
class PlannedAction:
    actuator: str
    target: str
    reason: str
    kwargs: dict = field(default_factory=dict)
    #: Set when policy forbids this action; it is planned but not offered.
    blocked_by: str | None = None


# Verdicts where an attacker is positioned between the device and its server.
# Healing the ARP binding is the first response for these, because it restores
# correct routing without disconnecting anything.
MITM_VERDICTS = {"data_integrity", "known_attack"}


#: Hosts that are not medical devices but must not be cut off either — the HIS,
#: PACS, the gateway, DNS. Blocking the information system is its own outage, so
#: these are protected exactly like devices are. Set as a comma-separated list in
#: system_config under this key.
PROTECTED_HOSTS_KEY = "enforcement.protected_hosts"

DEVICE = "medical_device"
INFRASTRUCTURE = "protected_infrastructure"
UNKNOWN = "unknown"


def _protected_hosts(db: Session) -> set[str]:
    from models.system_config import SystemConfig

    row = db.query(SystemConfig).filter(SystemConfig.config_key == PROTECTED_HOSTS_KEY).first()
    if row is None or not row.config_value:
        return set()
    return {value.strip() for value in row.config_value.split(",") if value.strip()}


def classify(ip: str | None, devices_by_ip: dict, protected: set[str]) -> str:
    if ip is None:
        return UNKNOWN
    if ip in devices_by_ip:
        return DEVICE
    if ip in protected:
        return INFRASTRUCTURE
    return UNKNOWN


def identify_adversary(db: Session, *, alert: Alert) -> Adversary:
    """Works out which end of the conversation is hostile — or admits it cannot.

    Direction alone does not decide this. A registered device SENDING to an
    unknown host might be the victim of a MITM or might be compromised and
    beaconing out; one flow does not distinguish them. Worse, the other end is
    often the HIS — blocking that is a hospital-wide outage, not a mitigation.

    So the rule is by role, not by direction: act on the end nobody has vouched
    for, and when both ends are known, name no target and say why.
    """
    detection = db.query(Detection).filter(Detection.id == alert.detection_id).first()
    flow = db.query(NetworkFlow).filter(NetworkFlow.id == detection.flow_id).first() if detection else None
    device = db.query(Device).filter(Device.id == alert.device_id).first() if alert.device_id else None

    if flow is None:
        return Adversary(ip=None, rationale="no flow recorded for this alert")

    # The registry is what makes this decision safe: we compare observed traffic
    # against what biomed entered at onboarding, not against a guess.
    devices_by_ip = {d.ip_address: d for d in db.query(Device).filter(Device.ip_address.isnot(None))}
    protected = _protected_hosts(db)

    src_role = classify(flow.src_ip, devices_by_ip, protected)
    dst_role = classify(flow.dst_ip, devices_by_ip, protected)

    def as_device(ip: str, why: str) -> Adversary:
        found = devices_by_ip[ip]
        return Adversary(
            ip=ip, rationale=why, is_registered_device=True, device=found,
            life_critical=bool(found.device_type and found.device_type.is_life_critical),
        )

    # Exactly one end is a stranger — that is the adversary, whichever direction
    # the packets went.
    if src_role == UNKNOWN and dst_role != UNKNOWN:
        other = devices_by_ip.get(flow.dst_ip)
        return Adversary(
            ip=flow.src_ip,
            rationale=(f"{flow.src_ip} is not a registered device or known infrastructure, and was "
                       f"talking to {other.device_uid if other else flow.dst_ip}; "
                       f"the known host is the one to protect"),
        )
    if dst_role == UNKNOWN and src_role != UNKNOWN:
        other = devices_by_ip.get(flow.src_ip)
        beaconing = f"{other.device_uid} may itself be compromised and reaching out — " if other else ""
        return Adversary(
            ip=flow.dst_ip,
            rationale=(f"{beaconing}{flow.dst_ip} is not a registered device or known "
                       f"infrastructure. Confirm it is not a legitimate server that was simply "
                       f"never registered before blocking it."),
        )

    # Both ends are strangers: nothing here is ours to protect, and nothing here
    # is confidently the attacker either.
    if src_role == UNKNOWN and dst_role == UNKNOWN:
        return Adversary(
            ip=flow.src_ip,
            rationale=(f"neither {flow.src_ip} nor {flow.dst_ip} is registered — this traffic may "
                       f"not involve a medical device at all. Verify before acting."),
        )

    # Both ends are known. If Stage 4 says the readings are forged while the
    # device's own address is in use, someone is impersonating it — and the fix
    # is to restore the binding, not to disconnect the victim.
    if detection is not None and detection.stage4_injection_suspected and device is not None:
        return Adversary(
            ip=device.ip_address,
            rationale=(f"vitals from {device.device_uid} are implausible while its own address is "
                       f"in use — consistent with an attacker impersonating it. Restore the "
                       f"registered MAC/IP binding; do not disconnect the device."),
        )

    # Both known, no impersonation signal: the sending device is the best
    # candidate for "compromised", but it is still ours, so it is gated.
    if src_role == DEVICE:
        return as_device(
            flow.src_ip,
            f"{devices_by_ip[flow.src_ip].device_uid} is the source of this traffic and both ends "
            f"are known hosts — treat the device as possibly compromised, but confirm it before "
            f"cutting off a device a patient is on",
        )

    return Adversary(
        ip=None,
        rationale=(f"both {flow.src_ip} and {flow.dst_ip} are protected hosts; there is no safe "
                   f"target here. Investigate rather than block."),
    )


def plan(db: Session, *, alert: Alert) -> dict:
    """What could be done about this alert, and what policy allows.

    Returns the plan without doing any of it. The console shows this so an
    analyst sees the reasoning — especially who would be acted on — before
    anything happens.
    """
    adversary = identify_adversary(db, alert=alert)
    detection = db.query(Detection).filter(Detection.id == alert.detection_id).first()
    device = db.query(Device).filter(Device.id == alert.device_id).first() if alert.device_id else None
    actions: list[PlannedAction] = []

    verdict = detection.final_verdict if detection else None

    # ARP healing comes first for the MITM cases: it restores correct routing and
    # disconnects nobody, so it is the only action that is strictly safe.
    if verdict in MITM_VERDICTS and device is not None and device.mac_address and device.ip_address:
        actions.append(PlannedAction(
            actuator="arp_heal",
            target=device.ip_address,
            reason=f"restore the registered binding for {device.device_uid}",
            kwargs={"correct_mac": device.mac_address},
        ))

    if adversary.ip:
        protected = _protected_hosts(db)
        blocked = None
        if adversary.is_registered_device and adversary.life_critical:
            # The hard stop. A ventilator is not taken off the network by a rule.
            blocked = (f"{adversary.device.device_uid} is life-critical — a person must decide "
                       f"this, and should isolate the ward segment rather than the device")
        elif adversary.is_registered_device:
            blocked = (f"{adversary.device.device_uid} is a registered medical device; confirm "
                       f"it is compromised rather than impersonated before cutting it off")
        elif adversary.ip in protected:
            # Blocking the HIS stops every ward from charting. That is a bigger
            # incident than the one being responded to.
            blocked = (f"{adversary.ip} is protected infrastructure — blocking it would take out "
                       f"a service the whole hospital depends on")

        actions.append(PlannedAction(
            actuator="switch_port", target=adversary.ip,
            reason=f"isolate the adversary at the access port ({adversary.rationale})",
            blocked_by=blocked,
        ))
        actions.append(PlannedAction(
            actuator="firewall", target=adversary.ip,
            reason=f"block the adversary upstream ({adversary.rationale})",
            blocked_by=blocked,
        ))

    if device is not None and device.mqtt_client_id and verdict == "data_integrity":
        # The same trap as blocking an IP: this client id belongs to the medical
        # device. Revoking it is right only when the credentials have been cloned
        # and something else is publishing as the device. If the readings are
        # being altered in transit, the device is the victim and revoking it
        # silences the real monitor while the attacker carries on.
        actions.append(PlannedAction(
            actuator="mqtt_revoke", target=device.mqtt_client_id,
            reason=(f"stop anything publishing as {device.device_uid}. Only do this if the "
                    f"credentials were cloned — if the readings are being altered in transit, "
                    f"this disconnects the real device and changes nothing for the attacker."),
            blocked_by=(
                f"{device.mqtt_client_id} is {device.device_uid}'s own client id"
                + (" and it is life-critical" if device.device_type
                   and device.device_type.is_life_critical else "")
                + ". Confirm the credentials were cloned before revoking them."
            ),
        ))

    state = enforcement.status(db)
    return {
        "alert_uid": alert.alert_uid,
        "verdict": verdict,
        "adversary": {
            "ip": adversary.ip,
            "rationale": adversary.rationale,
            "is_registered_device": adversary.is_registered_device,
            "device_uid": adversary.device.device_uid if adversary.device else None,
            "life_critical": adversary.life_critical,
        },
        "enforcement_enabled": state["enforcement_enabled"],
        "actions": [
            {
                "actuator": a.actuator,
                "target": a.target,
                "reason": a.reason,
                "blocked_by": a.blocked_by,
                "available": next((s["configured"] for s in state["actuators"]
                                   if s["name"] == a.actuator), False),
                "would_be_live": next((s["live"] for s in state["actuators"]
                                       if s["name"] == a.actuator), False),
            }
            for a in actions
        ],
    }


def execute(db: Session, *, alert: Alert, actuator_name: str,
            confirm_medical_device: bool = False) -> dict:
    """Carries out one planned action, after checking policy allows it."""
    plan_result = plan(db, alert=alert)
    chosen = next((a for a in plan_result["actions"] if a["actuator"] == actuator_name), None)
    if chosen is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"'{actuator_name}' is not part of the plan for this alert — "
            f"available: {', '.join(a['actuator'] for a in plan_result['actions']) or 'none'}",
        )

    if chosen["blocked_by"] and not confirm_medical_device:
        raise HTTPException(status.HTTP_409_CONFLICT, chosen["blocked_by"])

    actuator = enforcement.load(db, actuator_name)
    if actuator is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown actuator '{actuator_name}'")

    result = actuator.execute(target=chosen["target"], reason=chosen["reason"],
                              **_kwargs_for(db, alert, actuator_name))
    return {
        "actuator": result.actuator,
        "target": result.target,
        "succeeded": result.succeeded,
        "dry_run": result.dry_run,
        "detail": result.detail,
        "summary": str(result),
        "adversary": plan_result["adversary"],
    }


def _kwargs_for(db: Session, alert: Alert, actuator_name: str) -> dict:
    """Extra arguments an actuator needs, looked up rather than passed in.

    ARP healing needs the registered MAC, and it has to come from the registry —
    accepting it from the caller would let a request assert any binding it liked.
    """
    if actuator_name != "arp_heal":
        return {}
    device = db.query(Device).filter(Device.id == alert.device_id).first() if alert.device_id else None
    return {"correct_mac": device.mac_address if device else ""}
