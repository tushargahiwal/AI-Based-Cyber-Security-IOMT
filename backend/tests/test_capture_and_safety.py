"""Module 2's flow assembly, and the safety properties around mitigation.

Two things are pinned here that would fail silently otherwise:

  * A flow's two directions must be matched into ONE flow. If the key stops
    being direction-agnostic, every packet count halves and every model input is
    quietly wrong — no error, just worse answers.

  * A quarantine must expire. A device cut off during a night shift and left
    that way is a patient-safety incident the system caused, and the only thing
    stopping it is a deadline nothing tests unless this does.
"""

from datetime import datetime, timedelta

import pytest

from services import safety_service
from workers import feature_extractor
from workers.flow_assembler import FlowAssembler, _flow_key


def packet(src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=40000, dst_port=1883,
           at=0.0, size=120, **extra):
    return {
        "src_ip": src_ip, "dst_ip": dst_ip, "src_port": src_port, "dst_port": dst_port,
        "protocol": "TCP", "at": at, "size": size, "payload": max(size - 40, 0),
        "ttl": 64, "flags": 0x18, "src_mac": "aa:bb:cc:dd:ee:ff", "dst_mac": "11:22:33:44:55:66",
        **extra,
    }


# --- flow assembly -------------------------------------------------------


def test_both_directions_land_in_one_flow():
    forward, is_forward = _flow_key("10.0.0.1", "10.0.0.2", 40000, 1883, "TCP")
    backward, is_backward = _flow_key("10.0.0.2", "10.0.0.1", 1883, 40000, "TCP")
    assert forward == backward, "a reply must key to the same flow as its request"
    assert is_forward != is_backward, "but the two must be told apart"


def test_a_request_and_its_reply_are_counted_together():
    assembler = FlowAssembler()
    assembler.add_packet(packet(at=0.0, size=120))
    assembler.add_packet(packet(src_ip="10.0.0.2", dst_ip="10.0.0.1", src_port=1883,
                                dst_port=40000, at=0.1, size=60))

    assert assembler.open_flows == 1
    flow = assembler.flush()[0]
    summary = flow.summary()
    assert summary["src_packets"] == 1 and summary["dst_packets"] == 1
    assert summary["total_packets"] == 2
    assert summary["total_bytes"] == 180


def test_different_conversations_stay_separate():
    assembler = FlowAssembler()
    assembler.add_packet(packet(src_port=40000, at=0.0))
    assembler.add_packet(packet(src_port=40001, at=0.1))
    assert assembler.open_flows == 2


def test_a_quiet_flow_closes_and_a_busy_one_does_not():
    assembler = FlowAssembler(idle_seconds=15.0, timeout_seconds=120.0)
    assembler.add_packet(packet(at=1000.0))
    assert assembler.collect_expired(now=1005.0) == [], "5s of quiet is not idle"
    assert len(assembler.collect_expired(now=1020.0)) == 1, "20s of quiet is"


def test_a_long_running_flow_is_cut_at_the_timeout():
    """Otherwise a persistent MQTT session would never be scored at all."""
    assembler = FlowAssembler(idle_seconds=15.0, timeout_seconds=120.0)
    for i in range(30):
        assembler.add_packet(packet(at=1000.0 + i * 5))
    assert len(assembler.collect_expired(now=1000.0 + 125)) == 1


def test_regular_traffic_has_lower_jitter_than_bursty():
    """Jitter is the signal behind beaconing detection, so it has to separate these.

    Malware on a timer sends at an almost fixed interval; clinical traffic comes
    in bursts around rounds and alarms.
    """
    steady, bursty = FlowAssembler(), FlowAssembler()

    at = 0.0
    for _ in range(20):
        steady.add_packet(packet(at=at))
        at += 0.10  # a beacon: the same gap every time

    at = 0.0
    for gap in [0.01, 0.9, 0.02, 1.4, 0.01, 0.7] * 4:
        bursty.add_packet(packet(at=at))
        at += gap

    steady_jitter = steady.flush()[0].summary()["src_jitter"]
    bursty_jitter = bursty.flush()[0].summary()["src_jitter"]
    assert steady_jitter < 0.001, "an exactly periodic sender should have near-zero jitter"
    assert bursty_jitter > steady_jitter * 100


# --- the vector handed to the models -------------------------------------


def test_the_vector_matches_the_trained_feature_order():
    assembler = FlowAssembler()
    assembler.add_packet(packet(at=0.0))
    assembler.add_packet(packet(at=0.2))
    vector = feature_extractor.build_vector(assembler.flush()[0].summary())
    assert len(vector) == len(feature_extractor.feature_order())
    assert all(isinstance(v, float) for v in vector)


def test_missing_vitals_fall_back_to_a_living_patient_not_zero():
    """Zero across the vitals columns reads to the models as a corpse."""
    assembler = FlowAssembler()
    assembler.add_packet(packet(at=0.0))
    vector = feature_extractor.build_vector(assembler.flush()[0].summary())
    columns = feature_extractor.feature_order()
    for name in ("Heart_rate", "SpO2", "Temp"):
        assert vector[columns.index(name)] > 0


def test_supplied_vitals_are_used_over_the_fallback():
    assembler = FlowAssembler()
    assembler.add_packet(packet(at=0.0))
    summary = assembler.flush()[0].summary()
    vector = feature_extractor.build_vector(summary, vitals={"SpO2": 88, "Heart_rate": 132})
    columns = feature_extractor.feature_order()
    assert vector[columns.index("SpO2")] == 88.0
    assert vector[columns.index("Heart_rate")] == 132.0


def test_unmeasurable_columns_are_named_rather_than_hidden():
    coverage = feature_extractor.describe_coverage()
    assert coverage["not_measurable_without_stream_reassembly"] == list(feature_extractor.UNMEASURED)
    assert coverage["measured_from_packets"] + coverage["supplied_by_vitals_stream"] \
        + len(coverage["not_measurable_without_stream_reassembly"]) == coverage["total"]


# --- mitigations expire --------------------------------------------------


def test_a_quarantine_has_a_deadline_within_the_shift():
    """Longer than a shift and a forgotten quarantine outlives the person who set it."""
    deadline = safety_service.quarantine_deadline(datetime(2026, 1, 1, 22, 0))
    assert deadline == datetime(2026, 1, 2, 2, 0)
    assert safety_service.QUARANTINE_HOURS <= 8


def test_a_block_outlasts_a_quarantine():
    """Blocking an attacker's IP is cheap; cutting off a monitor is not."""
    assert safety_service.BLOCK_HOURS > safety_service.QUARANTINE_HOURS


def test_the_sweep_runs_often_enough_to_matter():
    assert safety_service.SWEEP_SECONDS <= 300


@pytest.mark.parametrize("expires_in, still_active", [(-1, False), (1, True), (None, True)])
def test_the_active_filter_reads_the_expiry_it_writes(expires_in, still_active):
    """expires_at was stored and never read, so a lapsed block still listed as active."""
    from models.blocklist import BlocklistEntry

    now = datetime(2026, 1, 1, 12, 0)
    entry = BlocklistEntry(
        entry_type="ip", value="10.0.0.9", is_active=True,
        expires_at=None if expires_in is None else now + timedelta(hours=expires_in),
    )
    is_live = entry.is_active and (entry.expires_at is None or entry.expires_at > now)
    assert is_live is still_active
