"""Live packet capture (doc §11, Module 2).

Captures on an interface with Scapy's AsyncSniffer, assembles flows, scores each
closed flow through the same pipeline the API uses, and writes the detections.
This is what makes the project an appliance rather than a console.

Deployment shape it is written for: a mirror/SPAN port on the switch that serves
the ward, NOT inline. If this process hangs, crashes or is killed, traffic to the
ventilator is unaffected — it never carried that traffic in the first place. In a
hospital that property is not a nicety, it is the reason the box is allowed on
the network at all.

Also reads a .pcap offline, through the same code path, so what is tested is what
runs.

    sudo ./venv/bin/python -m workers.sniffer --interface eth0
    ./venv/Scripts/python.exe -m workers.sniffer --pcap capture.pcap --dry-run

Root/Administrator is needed for live capture; a pcap is not. On Windows,
Npcap must be installed.
"""

import argparse
import signal
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from database import SessionLocal  # noqa: E402
from models.device import Device  # noqa: E402
from models.vital_reading import VitalReading  # noqa: E402
from services import detection_service  # noqa: E402
from workers import feature_extractor  # noqa: E402
from workers.flow_assembler import FlowAssembler  # noqa: E402

# How often closed flows are collected and scored. Well under the 15 s idle
# timeout, so a finished conversation is scored while it still matters.
DRAIN_SECONDS = 2.0

PROTOCOL_NAMES = {6: "TCP", 17: "UDP", 1: "ICMP"}
MQTT_PORTS = {1883, 8883}


def describe(packet) -> dict | None:
    """Scapy packet -> the plain dict FlowAssembler consumes.

    Returns None for anything without an IP layer (ARP, LLDP, spanning tree).
    Those are not flows; ARP in particular is watched separately, since ARP
    spoofing is one of the attacks we care about.
    """
    from scapy.layers.inet import ICMP, IP, TCP, UDP
    from scapy.layers.l2 import Ether

    if IP not in packet:
        return None

    ip = packet[IP]
    protocol_number = ip.proto
    src_port = dst_port = 0
    flags = 0

    if TCP in packet:
        src_port, dst_port = int(packet[TCP].sport), int(packet[TCP].dport)
        flags = int(packet[TCP].flags)
    elif UDP in packet:
        src_port, dst_port = int(packet[UDP].sport), int(packet[UDP].dport)
    elif ICMP not in packet:
        return None

    protocol = PROTOCOL_NAMES.get(protocol_number, "OTHER")
    if protocol in ("TCP", "UDP") and (src_port in MQTT_PORTS or dst_port in MQTT_PORTS):
        protocol = "MQTT"

    ether = packet.getlayer(Ether)
    return {
        "at": float(packet.time),
        "src_ip": ip.src,
        "dst_ip": ip.dst,
        "src_port": src_port,
        "dst_port": dst_port,
        "protocol": protocol,
        "src_mac": ether.src if ether else None,
        "dst_mac": ether.dst if ether else None,
        "size": len(packet),
        "payload": max(len(ip.payload) - 20, 0),
        "ttl": int(ip.ttl),
        "flags": flags,
    }


class DeviceResolver:
    """Maps an observed IP to a registered device, and notices when its MAC changes.

    The MAC check is the live version of the arp_binding_violation feature. In
    the WUSTL capture that feature is unusable — the attacker used one fixed MAC
    so it reproduces the label exactly — but here the binding comes from the
    device registry, filled in at onboarding and independent of any attack. That
    is what makes it real evidence rather than a leak.
    """

    def __init__(self, db, refresh_seconds: float = 60.0):
        self.db = db
        self.refresh_seconds = refresh_seconds
        self._by_ip: dict[str, tuple[int, str | None, str]] = {}
        self._loaded_at = 0.0
        self.binding_violations: dict[str, str] = {}

    def _refresh(self) -> None:
        rows = self.db.query(Device.id, Device.ip_address, Device.mac_address,
                             Device.device_uid).all()
        self._by_ip = {ip: (did, mac, uid) for did, ip, mac, uid in rows if ip}
        self._loaded_at = time.time()

    def resolve(self, ip: str, observed_mac: str | None) -> int | None:
        if time.time() - self._loaded_at > self.refresh_seconds:
            self._refresh()
        entry = self._by_ip.get(ip)
        if entry is None:
            return None
        device_id, registered_mac, device_uid = entry
        if registered_mac and observed_mac and observed_mac.lower() != registered_mac.lower():
            self.binding_violations[device_uid] = observed_mac
        return device_id


def latest_vitals(db, device_id: int | None) -> dict | None:
    """The device's most recent reading, for the vitals columns of the vector."""
    if device_id is None:
        return None
    reading = (
        db.query(VitalReading)
        .filter(VitalReading.device_id == device_id)
        .order_by(VitalReading.recorded_at.desc())
        .first()
    )
    if reading is None:
        return None
    return {
        "Heart_rate": reading.heart_rate,
        "Pulse_Rate": reading.heart_rate,
        "SpO2": reading.spo2,
        "SYS": reading.systolic_bp,
        "DIA": reading.diastolic_bp,
        "Temp": float(reading.body_temp) if reading.body_temp is not None else None,
        "Resp_Rate": reading.respiration_rate,
    }


def run(*, interface: str | None, pcap: str | None, dry_run: bool,
        bpf: str | None, limit: int | None, quiet: bool) -> None:
    from scapy.all import AsyncSniffer, sniff

    assembler = FlowAssembler()
    counters = defaultdict(int)
    stop = threading.Event()
    db = SessionLocal()
    resolver = DeviceResolver(db)

    def handle(packet):
        info = describe(packet)
        if info is not None:
            assembler.add_packet(info)
        else:
            counters["non_ip_packets"] += 1

    def score(flow) -> None:
        summary = flow.summary()
        counters["flows"] += 1

        device_id = resolver.resolve(summary["src_ip"], summary["src_mac"])
        if device_id is None:
            device_id = resolver.resolve(summary["dst_ip"], summary["dst_mac"])

        vector = feature_extractor.build_vector(summary, vitals=latest_vitals(db, device_id))

        if dry_run:
            counters["scored"] += 1
            if not quiet:
                print(f"  {summary['src_ip']}:{summary['src_port']} -> "
                      f"{summary['dst_ip']}:{summary['dst_port']} {summary['protocol']:<5} "
                      f"{summary['total_packets']:>4}pkt {summary['total_bytes']:>7}B "
                      f"{summary['duration']:>6.2f}s  device={device_id or '-'} (dry run)")
            return

        try:
            result = detection_service.submit_detection(
                db,
                flow_uid=None,
                device_id=device_id,
                feature_vector=vector,
                feature_set_version="v1",
                src_ip=summary["src_ip"],
                dst_ip=summary["dst_ip"],
                protocol=summary["protocol"] if summary["protocol"] in
                ("TCP", "UDP", "ICMP", "MQTT", "HTTP", "BLE") else "OTHER",
                capture_source="live" if interface else "pcap",
            )
        except Exception as exc:
            # One bad flow must not stop the capture. The models are the most
            # likely thing to reject a vector, and losing the sniffer over it
            # would mean losing every flow after it too.
            counters["errors"] += 1
            db.rollback()
            if not quiet:
                print(f"  ! scoring failed: {type(exc).__name__}: {exc}")
            return

        detection = result["detection"]
        counters["scored"] += 1
        counters[detection.final_verdict] += 1
        if result["alert"] is not None:
            counters["alerts"] += 1
        if not quiet and (detection.final_verdict != "benign" or counters["scored"] % 25 == 0):
            print(f"  {summary['src_ip']} -> {summary['dst_ip']} {summary['protocol']:<5} "
                  f"p={float(detection.stage1_probability):.3f} -> "
                  f"{detection.final_verdict:<17}{' ALERT' if result['alert'] else ''}")

    def drain(now: float | None = None) -> None:
        for flow in assembler.collect_expired(now):
            score(flow)

    if pcap:
        print(f"Reading {pcap} ...")
        # No BPF here on purpose: it is a kernel capture filter, and applying it
        # to a file makes Scapy shell out to tcpdump, which is not present on a
        # plain Windows install. describe() already discards non-IP packets, so
        # offline reads are filtered in Python instead.
        sniff(offline=pcap, prn=handle, store=False, count=limit or 0)
        print(f"  {counters['non_ip_packets']} non-IP packets skipped, "
              f"{assembler.stats['packets']} packets in {assembler.stats['flows_opened']} flows")
        for flow in assembler.flush():
            score(flow)
    else:
        print(f"Capturing on {interface} ...  (Ctrl-C to stop)")
        print("  a mirror/SPAN port is expected — this process is not in the traffic path")
        sniffer = AsyncSniffer(iface=interface, prn=handle, store=False, filter=bpf)
        sniffer.start()

        def on_signal(*_):
            stop.set()

        signal.signal(signal.SIGINT, on_signal)
        try:
            while not stop.is_set():
                stop.wait(DRAIN_SECONDS)
                drain()
                if limit and counters["scored"] >= limit:
                    break
        finally:
            sniffer.stop()
            for flow in assembler.flush():
                score(flow)

    print(f"\npackets={assembler.stats['packets']} flows={counters['flows']} "
          f"scored={counters['scored']} alerts={counters['alerts']} errors={counters['errors']}")
    verdicts = {k: v for k, v in counters.items()
                if k in ("benign", "known_attack", "zero_day_suspect", "data_integrity", "uncertain")}
    if verdicts:
        print("verdicts: " + ", ".join(f"{k}={v}" for k, v in sorted(verdicts.items())))
    if resolver.binding_violations:
        print("\nMAC/IP binding violations (possible ARP spoofing):")
        for uid, mac in resolver.binding_violations.items():
            print(f"  {uid}: observed {mac}, which is not its registered MAC")
    db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--interface", help="interface to capture on (needs root/Administrator)")
    source.add_argument("--pcap", help="read a capture file instead of the wire")
    parser.add_argument("--bpf", default="ip", help="BPF capture filter (default: ip)")
    parser.add_argument("--limit", type=int, default=None, help="stop after this many flows")
    parser.add_argument("--dry-run", action="store_true",
                        help="assemble and print flows without scoring or writing anything")
    parser.add_argument("--quiet", action="store_true", help="totals only")
    args = parser.parse_args()

    coverage = feature_extractor.describe_coverage()
    print(f"Feature coverage: {coverage['measured_from_packets']} of {coverage['total']} "
          f"from packets, {coverage['supplied_by_vitals_stream']} from the vitals stream, "
          f"{len(coverage['not_measurable_without_stream_reassembly'])} not measurable here")

    run(interface=args.interface, pcap=args.pcap, dry_run=args.dry_run,
        bpf=args.bpf, limit=args.limit, quiet=args.quiet)


if __name__ == "__main__":
    main()
