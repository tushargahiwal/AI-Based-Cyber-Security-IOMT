"""The 10 IoMT-specific engineered features from doc §7.2.

These do not exist in the standard CIC/WUSTL feature sets. They are the part of
this project that is ours rather than the dataset's, so what each one needs is
stated explicitly and checked, not assumed.

Five of the ten can be computed from WUSTL-EHMS-2020. The other five need
information the capture simply does not carry — raw payload bytes, IP TTL, MQTT
control-packet types, wall-clock timestamps. Rather than fabricate them (a zero
column would silently look like a real feature and quietly weaken every model
that trains on it), they are declared UNAVAILABLE here and skipped, and the
detection path computes them at runtime where the live packet does carry them.

    computable from WUSTL          needs data WUSTL does not have
    ---------------------          -----------------------------
    interarrival_regularity        ttl_deviation          (no TTL column)
    vitals_physio_violation        payload_entropy        (no payload bytes)
    vitals_delta_rate              mqtt_connect_ratio     (no MQTT control types)
    device_profile_deviation       mqtt_pub_no_sub        (no MQTT topics)
    arp_binding_violation          night_hour_flag        (no timestamps)
"""

import numpy as np
import pandas as pd

# Physiologically survivable ranges. Outside these a reading is not a sick
# patient, it is a broken or tampered sensor — which is the point of the feature.
PHYSIOLOGICAL_RANGES = {
    "Heart_rate": (20, 250),
    "SpO2": (50, 100),
    "SYS": (50, 250),
    "DIA": (20, 150),
    "Temp": (30.0, 43.0),
    "Resp_Rate": (4, 60),
}

VITALS = list(PHYSIOLOGICAL_RANGES)

AVAILABLE = [
    "interarrival_regularity",
    "vitals_physio_violation",
    "vitals_delta_rate",
    "device_profile_deviation",
    "arp_binding_violation",
]

# Above this agreement with the label, a single feature is not detecting an
# attack, it is *being* the label — see arp_binding_violation. 0.98 leaves room
# for a genuinely excellent feature while catching an identifier in disguise.
LEAKAGE_AGREEMENT_LIMIT = 0.98

UNAVAILABLE = {
    "ttl_deviation": "WUSTL-EHMS-2020 carries no IP TTL column",
    "payload_entropy": "the capture is flow statistics only, with no payload bytes",
    "mqtt_connect_ratio": "no MQTT control-packet types in this capture",
    "mqtt_pub_no_sub": "no MQTT topic information in this capture",
    "night_hour_flag": "rows carry no wall-clock timestamp, only capture order",
}


def _clean_vitals(df: pd.DataFrame) -> pd.DataFrame:
    """Zeros are sensor dropouts, not readings — carried forward as everywhere else.

    Without this the physiological check would mostly be detecting dropouts,
    which is a different (and much less interesting) thing than tampering.
    """
    out = df[VITALS].copy()
    for v in VITALS:
        out[v] = out[v].replace(0, np.nan).ffill().bfill()
    return out


def interarrival_regularity(df: pd.DataFrame) -> pd.Series:
    """Coefficient of variation of packet inter-arrival times.

    Beaconing malware sends on a timer, so its CV collapses toward zero; human
    and clinical traffic is bursty and irregular. Source and destination
    directions are averaged because either side can be the beaconing one.
    """
    def cv(jitter, mean_interval):
        return jitter / mean_interval.replace(0, np.nan)

    src = cv(df["SrcJitter"], df["SIntPkt"])
    dst = cv(df["DstJitter"], df["DIntPkt"])
    return pd.concat([src, dst], axis=1).mean(axis=1).fillna(0.0)


def vitals_physio_violation(df: pd.DataFrame) -> pd.Series:
    """How many of the six vitals fall outside a survivable range.

    A count rather than a flag: one odd reading is a sensor glitch, four at once
    is a payload someone has rewritten.
    """
    vitals = _clean_vitals(df)
    violations = pd.Series(0, index=df.index, dtype=float)
    for name, (low, high) in PHYSIOLOGICAL_RANGES.items():
        violations += ((vitals[name] < low) | (vitals[name] > high)).astype(float)
    return violations


def vitals_delta_rate(df: pd.DataFrame) -> pd.Series:
    """Largest per-second change across the six vitals, in units of their own spread.

    Each vital changes on its own scale — a 3 bpm move is nothing, a 3 °C move is
    an emergency — so each delta is divided by that vital's own standard
    deviation before they are compared.
    """
    vitals = _clean_vitals(df)
    duration = df["Dur"].replace(0, np.nan)
    scaled = pd.DataFrame(index=df.index)
    for name in VITALS:
        spread = vitals[name].std()
        delta = vitals[name].diff().abs()
        scaled[name] = (delta / duration) / (spread if spread > 0 else 1.0)
    return scaled.max(axis=1).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def device_profile_deviation(flow: pd.DataFrame, benign_mask: pd.Series) -> pd.Series:
    """Euclidean distance from the benign baseline centroid, in standard deviations.

    Takes the model-ready numeric flow frame, not the raw capture — the baseline
    is a point in the same space the models work in, dummy columns included.

    The centroid and spread come from BENIGN ROWS ONLY. Fitting them on
    everything would pull the baseline toward the attacks and blunt exactly the
    signal this is meant to carry.
    """
    baseline = flow.loc[benign_mask]
    centre = baseline.mean()
    spread = baseline.std()

    # A feature this device has never varied still matters: if the baseline is a
    # constant and the current flow differs from it, that IS a deviation, and
    # dividing by a zero spread would silently discard it. Fall back to the
    # column's spread across all traffic; a column that is constant everywhere
    # carries no information and drops out on its own.
    fallback = flow.std()
    spread = spread.where(spread > 0, fallback)
    usable = spread > 0
    if not usable.any():
        return pd.Series(0.0, index=flow.index)

    z = (flow.loc[:, usable] - centre[usable]) / spread[usable]
    return np.sqrt((z.fillna(0.0) ** 2).sum(axis=1))


def arp_binding_violation(df: pd.DataFrame) -> pd.Series:
    """1 where a MAC/IP pair differs from the binding registered for that IP.

    DO NOT TRAIN ON THIS FEATURE WITH WUSTL-EHMS-2020. The capture was produced
    with one attacker host that used a single fixed MAC for every attack row and
    the victim used another, so `SrcMac != registered` is *identical* to the
    label — 2046 of 2046 attacks, 0 false positives. A model given this column
    scores 100% and has learned the attacker's network card, not an attack.

    That is the same leak preprocessing.py avoids by dropping SrcMac/DstMac as
    identifiers (doc §6.5); computing a feature from them reintroduces it through
    the back door. leakage_report() below catches this automatically rather than
    relying on anyone remembering.

    The function stays because it is not leaky in deployment: there the registry
    is the device inventory, filled in at onboarding and independent of any
    attack, and a MAC that stops matching is genuine evidence of ARP spoofing.
    """
    if not {"SrcAddr", "SrcMac"}.issubset(df.columns):
        return pd.Series(0.0, index=df.index)
    registered = df.groupby("SrcAddr")["SrcMac"].agg(lambda s: s.mode().iat[0])
    expected = df["SrcAddr"].map(registered)
    return (df["SrcMac"] != expected).astype(float)


def build(raw: pd.DataFrame, flow: pd.DataFrame, *, benign_mask: pd.Series) -> pd.DataFrame:
    """All computable engineered features, as a frame aligned to `raw`.

    `raw` is the original capture (vitals, jitter, MAC/IP); `flow` is the
    model-ready numeric matrix the profile baseline lives in. `benign_mask` must
    mark the rows the baseline may learn from — in training that is the benign
    TRAINING split, never validation or test.
    """
    return pd.DataFrame({
        "interarrival_regularity": interarrival_regularity(raw),
        "vitals_physio_violation": vitals_physio_violation(raw),
        "vitals_delta_rate": vitals_delta_rate(raw),
        "device_profile_deviation": device_profile_deviation(flow, benign_mask),
        "arp_binding_violation": arp_binding_violation(raw),
    }, index=raw.index)


def leakage_report(features: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    """Agreement between each feature (thresholded) and the label.

    A feature that reproduces the label almost exactly is an identifier wearing a
    feature's name. Checking every engineered column against the label before
    training is cheap, and it is the check that would have caught the WUSTL MAC
    leak on day one instead of after a suspicious 100% accuracy.

    Binary columns are compared directly; continuous ones are compared at their
    best possible threshold, so this is an upper bound on how much of the label a
    single feature can carry on its own.
    """
    agreement = {}
    for name in features.columns:
        col = features[name]
        if col.nunique() <= 2:
            values = (col != col.mode().iat[0]).astype(int)
            agreement[name] = max(float((values == y).mean()), float((1 - values == y).mean()))
            continue
        best = 0.0
        for q in np.linspace(0.01, 0.99, 99):
            cut = col.quantile(q)
            above = (col > cut).astype(int)
            best = max(best, float((above == y).mean()), float((1 - above == y).mean()))
        agreement[name] = best
    return agreement


def drop_leaky(features: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, dict[str, float]]:
    """Returns (features safe to train on, the ones removed and why)."""
    agreement = leakage_report(features, y)
    leaky = {n: a for n, a in agreement.items() if a >= LEAKAGE_AGREEMENT_LIMIT}
    return features.drop(columns=list(leaky)), leaky


def describe() -> str:
    lines = [f"{len(AVAILABLE)} of 10 engineered features are computable from this capture:"]
    lines += [f"  + {name}" for name in AVAILABLE]
    lines.append("Not computable here (the detection path computes these live instead):")
    lines += [f"  - {name}: {why}" for name, why in UNAVAILABLE.items()]
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
