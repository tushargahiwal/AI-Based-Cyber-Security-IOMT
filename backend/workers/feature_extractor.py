"""Turns an assembled flow into the vector the models expect (doc §11, Module 2).

The models were trained on WUSTL-EHMS-2020, whose columns Argus produced. This
maps our own measurements onto that exact column order, because a vector that is
merely the right LENGTH but in the wrong order scores confidently and wrongly —
the worst possible failure for a detector.

Three honest limits, each stated here rather than papered over:

  1. WUSTL rows carry the patient's vitals alongside the flow statistics, because
     that capture was one monitor's stream. Live, the vitals arrive separately on
     /api/v1/vitals, so they are supplied by the caller and default to the
     device's last known reading — not to zero, which would look to the models
     like a patient with no pulse.

  2. Loss/pLoss need TCP sequence tracking we deliberately do not do. They are
     reported as 0, and `UNMEASURED` names them so nobody mistakes that for a
     measurement.

  3. Dir_/Flgs_ are one-hot columns of Argus's own flag strings. We rebuild those
     strings from the TCP flag bits; a combination Argus never emitted lands in
     no column, which is correct — it is a pattern the model never saw.
"""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FEATURE_ORDER = _PROJECT_ROOT / "models" / "feature_order.json"

# Columns we cannot measure without TCP stream reassembly. Zero here is a stated
# absence, not a reading.
UNMEASURED = ("Loss", "pLoss", "pSrcLoss", "pDstLoss")

# The six vitals the capture carries, and a resting-adult value to fall back on
# when a device has not reported yet. Zero would read as a dead patient.
VITALS_DEFAULTS = {
    "Temp": 36.6, "SpO2": 97.0, "Pulse_Rate": 78.0,
    "SYS": 120.0, "DIA": 78.0, "Heart_rate": 78.0, "Resp_Rate": 16.0, "ST": 0.0,
}

FIN, SYN, RST, PSH, ACK, URG = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20

_features_cache: list[str] | None = None


def feature_order() -> list[str]:
    global _features_cache
    if _features_cache is None:
        with open(_FEATURE_ORDER) as f:
            _features_cache = json.load(f)["features"]
    return _features_cache


def argus_flag_string(flags: int) -> str:
    """Rebuilds Argus's flag mnemonic from raw TCP flag bits.

    Argus writes ' e        ' for an ordinary established exchange, ' eR' when a
    reset was seen, ' M' for multiple-record aggregates, and so on. The training
    columns are one-hot encodings of those exact strings, padding included, which
    is why the padding is reproduced rather than stripped.
    """
    letters = " e"
    if flags & RST:
        letters += "R"
    elif flags & FIN:
        letters += "F"
    elif flags & SYN and not flags & ACK:
        letters += "s"
    return letters.ljust(9)[:9]


def build_vector(flow_summary: dict, *, vitals: dict | None = None) -> list[float]:
    """One flow -> the model input vector, in feature_order.json's exact order.

    `vitals` is the device's most recent reading; anything missing falls back to
    a resting-adult value rather than to zero.
    """
    readings = {**VITALS_DEFAULTS, **{k: v for k, v in (vitals or {}).items() if v is not None}}
    s = flow_summary

    direction = "   ->"
    flag_string = argus_flag_string(s.get("src_flags", 0))

    values = {
        "Sport": float(s["src_port"]),
        "Dport": float(s["dst_port"]),
        "SrcBytes": float(s["src_bytes"]),
        "DstBytes": float(s["dst_bytes"]),
        "SrcLoad": float(s["src_load"]),
        "DstLoad": float(s["dst_load"]),
        "SrcGap": float(s["src_gap"]),
        "DstGap": float(s["dst_gap"]),
        # Argus reports inter-packet times in milliseconds.
        "SIntPkt": float(s["src_inter_pkt"] * 1000),
        "DIntPkt": float(s["dst_inter_pkt"] * 1000),
        # *Act variants are the active-period equivalents; without idle-period
        # separation they are the same measurement.
        "SIntPktAct": float(s["src_inter_pkt"] * 1000),
        "DIntPktAct": float(s["dst_inter_pkt"] * 1000),
        "SrcJitter": float(s["src_jitter"] * 1000),
        "DstJitter": float(s["dst_jitter"] * 1000),
        "sMaxPktSz": float(s["src_max_pkt"]),
        "dMaxPktSz": float(s["dst_max_pkt"]),
        "sMinPktSz": float(s["src_min_pkt"]),
        "dMinPktSz": float(s["dst_min_pkt"]),
        "Dur": float(s["duration"]),
        "Trans": float(s.get("transactions", 1)),
        "TotPkts": float(s["total_packets"]),
        "TotBytes": float(s["total_bytes"]),
        "Load": float(s["load"]),
        "Rate": float(s["rate"]),
        **{name: 0.0 for name in UNMEASURED},
        **{name: float(readings.get(name, 0.0)) for name in VITALS_DEFAULTS},
    }

    vector = []
    for column in feature_order():
        if column in values:
            vector.append(values[column])
        elif column.startswith("Dir_"):
            vector.append(1.0 if column == f"Dir_{direction}" else 0.0)
        elif column.startswith("Flgs_"):
            vector.append(1.0 if column == f"Flgs_{flag_string}" else 0.0)
        else:
            # A column the trainer produced that we have no source for. Zero is
            # the honest answer, and the name is worth knowing about.
            vector.append(0.0)
    return vector


def describe_coverage() -> dict:
    """What fraction of the trained feature set we can actually measure live."""
    columns = feature_order()
    measured, defaulted, absent = [], [], []
    for column in columns:
        if column in UNMEASURED:
            absent.append(column)
        elif column in VITALS_DEFAULTS:
            defaulted.append(column)
        else:
            measured.append(column)
    return {
        "total": len(columns),
        "measured_from_packets": len(measured),
        "supplied_by_vitals_stream": len(defaulted),
        "not_measurable_without_stream_reassembly": absent,
    }


if __name__ == "__main__":
    coverage = describe_coverage()
    print(f"{coverage['measured_from_packets']} of {coverage['total']} features come from packets")
    print(f"{coverage['supplied_by_vitals_stream']} come from the vitals stream")
    print(f"not measurable here: {', '.join(coverage['not_measurable_without_stream_reassembly'])}")
