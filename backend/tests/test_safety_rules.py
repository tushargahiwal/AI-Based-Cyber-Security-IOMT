"""The rules that stop the system from hurting a patient.

Two of these encode doc §14.3: a life-critical device is never cut off the
network automatically, and Stage 4 refuses to guess from an incomplete window.
Both are the kind of check that quietly stops being true during a refactor, so
they are pinned rather than trusted.
"""

import pytest
from fastapi import HTTPException

from services import alert_service, inference_service, report_service, simulation_service


# --- mitigation: which actions actually change system state ---------------


def test_enforcing_actions_are_exactly_the_ones_that_cut_traffic():
    assert alert_service.ENFORCING_ACTIONS == {"isolate_source", "block_ip", "revoke_mqtt_client"}


@pytest.mark.parametrize("action", ["notify_biomed", "manual_review", "force_reauth", "rate_limit"])
def test_advisory_actions_are_not_treated_as_enforcing(action):
    """These are carried out by a person off-platform.

    If one of them were ever classed as enforcing, applying it would demand the
    quarantine permission and a life-critical confirmation for what is really
    just ticking off a phone call.
    """
    assert action not in alert_service.ENFORCING_ACTIONS


def test_life_critical_devices_never_get_an_automatable_recommendation():
    """doc §14.3, checked through the generator rather than by reading it."""
    added = []

    class FakeSession:
        def add_all(self, rows):
            added.extend(rows)

    class FakeDeviceType:
        is_life_critical = True

    class FakeDevice:
        device_uid = "VENT-ICU1-003"
        ip_address = "10.0.0.9"
        device_type = FakeDeviceType()

    class FakeAlert:
        id = 1

    class FakeAttackType:
        code = "SPOOFING_MITM"

    alert_service._generate_recommendations(
        FakeSession(), FakeAlert(), attack_type=FakeAttackType(), device=FakeDevice()
    )

    assert added, "spoofing on a device should produce recommendations"
    assert all(r.is_automatable is False for r in added)


def test_the_same_recommendation_is_automatable_on_an_ordinary_device():
    """Guards against the previous test passing because nothing is ever automatable."""
    added = []

    class FakeSession:
        def add_all(self, rows):
            added.extend(rows)

    class FakeDeviceType:
        is_life_critical = False

    class FakeDevice:
        device_uid = "PULSEOX-GWA-001"
        ip_address = "10.0.0.15"
        device_type = FakeDeviceType()

    class FakeAlert:
        id = 1

    class FakeAttackType:
        code = "SPOOFING_MITM"

    alert_service._generate_recommendations(
        FakeSession(), FakeAlert(), attack_type=FakeAttackType(), device=FakeDevice()
    )
    assert any(r.is_automatable for r in added)


def test_data_integrity_recommendations_lead_with_the_clinical_step():
    added = []

    class FakeSession:
        def add_all(self, rows):
            added.extend(rows)

    class FakeAlert:
        id = 1

    alert_service._generate_recommendations(
        FakeSession(), FakeAlert(), attack_type=None, device=None, verdict="data_integrity"
    )
    assert added[0].action_type == "notify_biomed"


# --- Stage 4 refuses to guess from a partial window ----------------------


def test_stage4_rejects_a_short_window():
    window = [[80.0, 97.0, 120.0, 80.0, 36.5, 16.0]] * 10
    with pytest.raises(ValueError, match="31 readings"):
        inference_service.run_stage4(
            artifact_path="models/vitals_lstm_v1.keras",
            scaler_path="data/scalers/vitals_scaler_v1.pkl",
            window=window,
            threshold=3.0,
        )


def test_stage4_correlation_window_is_short_enough_to_mean_something():
    """A flag from an hour ago says nothing about the flow being scored now."""
    from services.vitals_service import STAGE4_CORRELATION_WINDOW

    assert STAGE4_CORRELATION_WINDOW.total_seconds() <= 15 * 60


# --- reports: no silently-invented time window ---------------------------


def test_daily_and_weekly_infer_their_own_window():
    start, end = report_service._resolve_period("daily", None, None)
    assert (end - start).days == 1
    start, end = report_service._resolve_period("weekly", None, None)
    assert (end - start).days == 7


@pytest.mark.parametrize("report_type", ["incident", "compliance", "custom"])
def test_open_ended_types_must_be_told_their_window(report_type):
    with pytest.raises(HTTPException) as exc:
        report_service._resolve_period(report_type, None, None)
    assert exc.value.status_code == 400


def test_a_backwards_period_is_refused():
    from datetime import datetime

    with pytest.raises(HTTPException) as exc:
        report_service._resolve_period(
            "custom", datetime(2026, 5, 2), datetime(2026, 5, 1)
        )
    assert exc.value.status_code == 400


# --- simulator: contiguous rows, or Stage 4 is meaningless ---------------


def test_simulation_picks_a_contiguous_run():
    import numpy as np
    import pandas as pd

    labels = [0] * 40 + [1] * 25 + [0] * 10 + [1] * 5
    raw = pd.DataFrame({"Label": labels})

    attack = simulation_service._select_indices(raw, "attack", 25)
    assert attack == list(range(40, 65)), "should take the longest attack run, unbroken"

    benign = simulation_service._select_indices(raw, "benign", 10)
    assert benign == list(range(0, 10))

    mixed = simulation_service._select_indices(raw, "mixed", 30)
    assert mixed == sorted(mixed) and len(set(mixed)) == len(mixed)
    assert np.array(labels)[mixed].min() == 0 and np.array(labels)[mixed].max() == 1, (
        "mixed should straddle the benign/attack boundary"
    )


def test_simulation_rejects_a_mode_the_capture_cannot_serve():
    import pandas as pd

    raw = pd.DataFrame({"Label": [0] * 20})
    with pytest.raises(HTTPException) as exc:
        simulation_service._select_indices(raw, "attack", 10)
    assert exc.value.status_code == 400
