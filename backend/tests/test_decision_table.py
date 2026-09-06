"""The doc §14.1 decision table — what verdict each combination of stages gives.

This is the single place where four model outputs become one call an analyst
acts on, so every branch is pinned here. A change that shifts a verdict should
have to change a test on purpose.
"""

import pytest

from services.detection_service import _decide


class FakeAttackType:
    def __init__(self, code="SPOOFING_MITM", default_severity="high"):
        self.code = code
        self.default_severity = default_severity


ANOMALOUS = {"is_anomaly": True, "reconstruction_error": 0.9, "anomaly_score": 2.6}
NORMAL = {"is_anomaly": False, "reconstruction_error": 0.1, "anomaly_score": 0.3}
INJECTION = {"injection_suspected": True, "max_zscore": 12.0, "threshold": 3.0}
VITALS_OK = {"injection_suspected": False, "max_zscore": 1.1, "threshold": 3.0}
CONFIDENT_STAGE2 = {"confidence": 0.91}


def decide(**overrides):
    kwargs = dict(
        stage1_probability=0.05,
        stage2=None,
        stage2_threshold=0.6,
        attack_type=None,
        stage3=NORMAL,
        stage4=VITALS_OK,
    )
    kwargs.update(overrides)
    return _decide(**kwargs)


# --- the ordinary path: no vitals evidence -------------------------------


def test_clean_flow_is_benign():
    assert decide() == ("benign", "info")


def test_confident_stage2_names_the_family_and_takes_its_severity():
    assert decide(
        stage1_probability=0.95,
        stage2=CONFIDENT_STAGE2,
        attack_type=FakeAttackType(default_severity="critical"),
    ) == ("known_attack", "critical")


def test_malicious_without_a_confident_family_is_uncertain():
    assert decide(stage1_probability=0.95, stage2={"confidence": 0.4},
                  attack_type=FakeAttackType()) == ("uncertain", "medium")


def test_malicious_and_anomalous_without_a_family_is_a_zero_day_suspect():
    assert decide(stage1_probability=0.95, stage3=ANOMALOUS) == ("zero_day_suspect", "high")


def test_clean_flow_that_the_autoencoder_dislikes_is_a_zero_day_suspect():
    assert decide(stage3=ANOMALOUS) == ("zero_day_suspect", "medium")


@pytest.mark.parametrize("probability", [0.35, 0.5, 0.65])
def test_the_uncertain_band_stays_low_severity_when_nothing_corroborates(probability):
    assert decide(stage1_probability=probability) == ("uncertain", "low")


def test_uncertain_band_plus_anomaly_escalates():
    assert decide(stage1_probability=0.5, stage3=ANOMALOUS) == ("zero_day_suspect", "medium")


# --- Stage 4 owns data_integrity ----------------------------------------


def test_implausible_vitals_and_malicious_traffic_is_the_strongest_case():
    verdict, severity = decide(
        stage1_probability=0.93,
        stage2=CONFIDENT_STAGE2,
        attack_type=FakeAttackType(default_severity="critical"),
        stage4=INJECTION,
    )
    assert verdict == "data_integrity"
    assert severity == "critical"


def test_implausible_vitals_on_malicious_traffic_defaults_to_high_without_a_family():
    assert decide(stage1_probability=0.93, stage4=INJECTION) == ("data_integrity", "high")


def test_implausible_vitals_in_the_uncertain_band_is_medium():
    assert decide(stage1_probability=0.5, stage4=INJECTION) == ("data_integrity", "medium")


def test_implausible_vitals_with_a_clean_flow_but_an_anomaly_is_medium():
    assert decide(stage3=ANOMALOUS, stage4=INJECTION) == ("data_integrity", "medium")


def test_implausible_vitals_alone_stays_low():
    """Vitals-only evidence must not page security.

    At z>3 the forecaster flags roughly 7% of benign windows, and a genuinely
    deteriorating patient looks the same as an injection. Low severity keeps it
    off the alert threshold, which is the behaviour the next test pins.
    """
    assert decide(stage4=INJECTION) == ("data_integrity", "low")


def test_vitals_only_evidence_does_not_reach_the_alert_threshold():
    from services.alert_service import ALERT_SEVERITIES

    _, severity = decide(stage4=INJECTION)
    assert severity not in ALERT_SEVERITIES


# --- degrading gracefully when stages are missing ------------------------


def test_stage4_absent_leaves_the_older_verdicts_untouched():
    with_stage4_off = decide(stage1_probability=0.95, stage2=CONFIDENT_STAGE2,
                             attack_type=FakeAttackType(), stage4=None)
    assert with_stage4_off == ("known_attack", "high")


def test_every_stage_missing_still_returns_a_verdict():
    assert decide(stage3=None, stage4=None) == ("benign", "info")
