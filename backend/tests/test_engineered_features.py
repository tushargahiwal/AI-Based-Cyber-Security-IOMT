"""The engineered features and, more importantly, the leak guard around them.

The WUSTL capture was produced with one attacker host using a fixed MAC, so
`arp_binding_violation` reproduces the label exactly — 2046 of 2046 attacks with
no false positives. A model trained on it scores 100% and has learned the
attacker's network card. That is the mistake preprocessing.py already avoids by
dropping SrcMac/DstMac as identifiers, and a derived feature reintroduced it.

These tests exist so the guard cannot quietly stop working: the second one fails
if the leak detector is ever loosened enough to let that column through.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml"))

import engineered_features as ef  # noqa: E402


def _capture(**overrides) -> pd.DataFrame:
    n = overrides.pop("n", 40)
    frame = pd.DataFrame({
        "SrcJitter": np.linspace(1.0, 2.0, n),
        "DstJitter": np.linspace(0.5, 1.5, n),
        "SIntPkt": np.full(n, 2.0),
        "DIntPkt": np.full(n, 4.0),
        "Dur": np.full(n, 1.0),
        "SrcAddr": ["10.0.0.1"] * n,
        "SrcMac": ["aa:bb:cc:dd:ee:ff"] * n,
        "Heart_rate": np.full(n, 80.0),
        "SpO2": np.full(n, 97.0),
        "SYS": np.full(n, 120.0),
        "DIA": np.full(n, 80.0),
        "Temp": np.full(n, 36.6),
        "Resp_Rate": np.full(n, 16.0),
    })
    for key, value in overrides.items():
        frame[key] = value
    return frame


# --- the leak guard ------------------------------------------------------


def test_a_feature_identical_to_the_label_is_caught():
    y = pd.Series([0] * 20 + [1] * 20)
    features = pd.DataFrame({"is_the_label_in_disguise": y.astype(float)})
    agreement = ef.leakage_report(features, y)
    assert agreement["is_the_label_in_disguise"] == pytest.approx(1.0)

    safe, leaky = ef.drop_leaky(features, y)
    assert "is_the_label_in_disguise" in leaky
    assert safe.empty


def test_the_inverse_of_the_label_is_caught_too():
    """A perfectly anti-correlated column carries just as much of the label."""
    y = pd.Series([0] * 20 + [1] * 20)
    features = pd.DataFrame({"inverted": (1 - y).astype(float)})
    assert ef.leakage_report(features, y)["inverted"] == pytest.approx(1.0)
    _, leaky = ef.drop_leaky(features, y)
    assert "inverted" in leaky


def test_a_merely_useful_feature_survives():
    """The guard must not eat a genuinely good feature — only an identifier."""
    rng = np.random.RandomState(0)
    y = pd.Series([0] * 200 + [1] * 200)
    signal = np.concatenate([rng.normal(0, 1, 200), rng.normal(1.2, 1, 200)])
    features = pd.DataFrame({"informative": signal})

    agreement = ef.leakage_report(features, y)["informative"]
    assert 0.6 < agreement < ef.LEAKAGE_AGREEMENT_LIMIT
    safe, leaky = ef.drop_leaky(features, y)
    assert not leaky and "informative" in safe.columns


def test_the_limit_leaves_room_for_a_strong_feature():
    assert 0.9 < ef.LEAKAGE_AGREEMENT_LIMIT < 1.0


# --- the features themselves ---------------------------------------------


def test_physiological_violations_are_counted_not_flagged():
    """One odd reading is a glitch; several at once is a rewritten payload."""
    frame = _capture(n=5)
    frame.loc[2, "Heart_rate"] = 400      # impossible
    frame.loc[2, "SpO2"] = 100            # fine
    frame.loc[3, "Heart_rate"] = 400
    frame.loc[3, "Temp"] = 50.0           # impossible

    violations = ef.vitals_physio_violation(frame)
    assert violations.iloc[0] == 0
    assert violations.iloc[2] == 1
    assert violations.iloc[3] == 2


def test_a_zero_vital_is_treated_as_a_dropout_not_a_violation():
    """Otherwise the feature would mostly be detecting broken sensors."""
    frame = _capture(n=5)
    frame.loc[3, "SpO2"] = 0
    assert ef.vitals_physio_violation(frame).iloc[3] == 0


def test_regular_traffic_scores_lower_than_bursty_traffic():
    steady = _capture(n=10, SrcJitter=np.full(10, 0.01), DstJitter=np.full(10, 0.01))
    bursty = _capture(n=10, SrcJitter=np.full(10, 5.0), DstJitter=np.full(10, 5.0))
    assert ef.interarrival_regularity(steady).mean() < ef.interarrival_regularity(bursty).mean()


def test_a_vitals_jump_raises_the_delta_rate():
    frame = _capture(n=10)
    frame.loc[6, "Heart_rate"] = 200      # sudden, physiologically implausible move
    rates = ef.vitals_delta_rate(frame)
    assert rates.iloc[6] > rates.iloc[5]


def test_profile_deviation_is_measured_from_the_benign_rows_only():
    flow = pd.DataFrame({"a": [0.0] * 10 + [50.0] * 5, "b": [1.0] * 10 + [90.0] * 5})
    benign = pd.Series([True] * 10 + [False] * 5)
    deviation = ef.device_profile_deviation(flow, benign)
    assert deviation.iloc[:10].max() < deviation.iloc[10:].min()


def test_arp_violation_fires_on_an_unexpected_mac():
    frame = _capture(n=10)
    frame.loc[7, "SrcMac"] = "de:ad:be:ef:00:01"
    violations = ef.arp_binding_violation(frame)
    assert violations.iloc[7] == 1
    assert violations.drop(index=7).sum() == 0


def test_unavailable_features_are_declared_rather_than_zero_filled():
    """A zero column would look like a real feature and weaken every model."""
    assert set(ef.UNAVAILABLE) == {
        "ttl_deviation", "payload_entropy", "mqtt_connect_ratio",
        "mqtt_pub_no_sub", "night_hour_flag",
    }
    built = ef.build(_capture(), pd.DataFrame({"a": np.arange(40.0)}),
                     benign_mask=pd.Series([True] * 40))
    assert not set(ef.UNAVAILABLE) & set(built.columns)
    assert set(built.columns) == set(ef.AVAILABLE)
