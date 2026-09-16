"""Groups packets into bidirectional flows and measures them (doc §11, Module 2).

This is the half of the capture path that turns "a stream of packets" into "a
row the models can score". A flow is one conversation: the same five-tuple in
either direction, closed when it goes quiet or when it has run long enough.

The measurements it produces are the ones the models were trained on, computed
the way Argus computed them for WUSTL-EHMS-2020 — because a feature that means
something slightly different at inference time than it did at training time is
worse than a missing feature. It is silently wrong.

Two things this deliberately does NOT do:

  * Reassemble TCP streams. Flow statistics do not need payload ordering, and
    reassembly is where a sniffer starts consuming more CPU than the traffic.
  * Decrypt anything. Everything here is derived from headers and timings.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field

# Argus, which produced the training capture, closes a flow after 120 s of life
# or 15 s of silence. Matching those keeps our flow boundaries comparable to the
# ones the models learned from.
FLOW_TIMEOUT_SECONDS = 120.0
FLOW_IDLE_SECONDS = 15.0

# TCP flag bits, in the order Argus reports them.
FIN, SYN, RST, PSH, ACK, URG = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20


@dataclass
class Direction:
    """One side of a conversation."""

    packets: int = 0
    bytes: int = 0
    payload_bytes: int = 0
    max_packet: int = 0
    min_packet: int = 0
    first_seen: float = 0.0
    last_seen: float = 0.0
    inter_arrivals: list = field(default_factory=list)
    ttls: list = field(default_factory=list)
    flags: int = 0

    def add(self, *, size: int, payload: int, at: float, ttl: int | None, flags: int) -> None:
        if self.packets == 0:
            self.first_seen = at
            self.min_packet = size
        else:
            self.inter_arrivals.append(at - self.last_seen)
            self.min_packet = min(self.min_packet, size)
        self.packets += 1
        self.bytes += size
        self.payload_bytes += payload
        self.max_packet = max(self.max_packet, size)
        self.last_seen = at
        self.flags |= flags
        if ttl is not None:
            self.ttls.append(ttl)

    @property
    def duration(self) -> float:
        return max(self.last_seen - self.first_seen, 0.0)

    def mean_inter_arrival(self) -> float:
        return sum(self.inter_arrivals) / len(self.inter_arrivals) if self.inter_arrivals else 0.0

    def jitter(self) -> float:
        """Mean absolute deviation of inter-arrival times, as Argus reports it."""
        if len(self.inter_arrivals) < 2:
            return 0.0
        mean = self.mean_inter_arrival()
        return sum(abs(gap - mean) for gap in self.inter_arrivals) / len(self.inter_arrivals)

    def load_bits_per_second(self) -> float:
        return (self.bytes * 8) / self.duration if self.duration > 0 else 0.0

    def gaps(self) -> int:
        """Inter-arrival gaps far above this direction's own norm.

        A stand-in for Argus's SrcGap/DstGap, which counts sequence-number holes.
        Without stream reassembly we cannot see those, so this counts timing
        holes instead — the same phenomenon seen from outside.
        """
        if len(self.inter_arrivals) < 3:
            return 0
        mean = self.mean_inter_arrival()
        return sum(1 for gap in self.inter_arrivals if gap > 4 * mean) if mean > 0 else 0


@dataclass
class Flow:
    key: tuple
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    src_mac: str | None = None
    dst_mac: str | None = None
    started_at: float = 0.0
    forward: Direction = field(default_factory=Direction)
    backward: Direction = field(default_factory=Direction)

    @property
    def last_seen(self) -> float:
        return max(self.forward.last_seen, self.backward.last_seen)

    @property
    def duration(self) -> float:
        return max(self.last_seen - self.started_at, 0.0)

    def is_expired(self, now: float) -> bool:
        return (now - self.last_seen) >= FLOW_IDLE_SECONDS or \
               (now - self.started_at) >= FLOW_TIMEOUT_SECONDS

    def summary(self) -> dict:
        """Everything a downstream consumer needs, in plain units.

        Deliberately not the model's feature vector — mapping these onto the
        trained feature order is feature_extractor's job, so the flow layer stays
        useful even if the model's inputs change.
        """
        f, b = self.forward, self.backward
        total_packets = f.packets + b.packets
        total_bytes = f.bytes + b.bytes
        duration = self.duration

        return {
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
            "src_mac": self.src_mac,
            "dst_mac": self.dst_mac,
            "started_at": self.started_at,
            "ended_at": self.last_seen,
            "duration": duration,
            "src_packets": f.packets,
            "dst_packets": b.packets,
            "total_packets": total_packets,
            "src_bytes": f.bytes,
            "dst_bytes": b.bytes,
            "total_bytes": total_bytes,
            "src_load": f.load_bits_per_second(),
            "dst_load": b.load_bits_per_second(),
            "load": (total_bytes * 8 / duration) if duration > 0 else 0.0,
            "rate": (total_packets / duration) if duration > 0 else 0.0,
            "src_gap": f.gaps(),
            "dst_gap": b.gaps(),
            "src_inter_pkt": f.mean_inter_arrival(),
            "dst_inter_pkt": b.mean_inter_arrival(),
            "src_jitter": f.jitter(),
            "dst_jitter": b.jitter(),
            "src_max_pkt": f.max_packet,
            "dst_max_pkt": b.max_packet,
            "src_min_pkt": f.min_packet,
            "dst_min_pkt": b.min_packet,
            "src_ttls": list(f.ttls),
            "dst_ttls": list(b.ttls),
            "src_flags": f.flags,
            "dst_flags": b.flags,
            "transactions": 1,
        }


def _flow_key(src_ip, dst_ip, src_port, dst_port, protocol):
    """A key that is the same for both directions of one conversation.

    Ordering the two endpoints means a reply is matched to its request instead
    of opening a second flow, which would halve every packet count.
    """
    a = (src_ip, src_port)
    b = (dst_ip, dst_port)
    forward = a <= b
    return ((a, b) if forward else (b, a), protocol), forward


class FlowAssembler:
    """Accumulates packets into flows and hands over the ones that have closed.

    Not thread-safe: the sniffer feeds it from one callback thread. Anything that
    wants the finished flows takes them through `collect_expired()`.
    """

    def __init__(self, *, idle_seconds: float = FLOW_IDLE_SECONDS,
                 timeout_seconds: float = FLOW_TIMEOUT_SECONDS):
        self.idle_seconds = idle_seconds
        self.timeout_seconds = timeout_seconds
        self._flows: dict[tuple, Flow] = {}
        self.stats = defaultdict(int)

    def add_packet(self, packet_info: dict) -> None:
        """Feeds one packet in. `packet_info` is what sniffer.describe() returns."""
        key, is_forward = _flow_key(
            packet_info["src_ip"], packet_info["dst_ip"],
            packet_info["src_port"], packet_info["dst_port"],
            packet_info["protocol"],
        )

        flow = self._flows.get(key)
        if flow is None:
            flow = Flow(
                key=key,
                src_ip=packet_info["src_ip"] if is_forward else packet_info["dst_ip"],
                dst_ip=packet_info["dst_ip"] if is_forward else packet_info["src_ip"],
                src_port=packet_info["src_port"] if is_forward else packet_info["dst_port"],
                dst_port=packet_info["dst_port"] if is_forward else packet_info["src_port"],
                protocol=packet_info["protocol"],
                src_mac=packet_info.get("src_mac"),
                dst_mac=packet_info.get("dst_mac"),
                started_at=packet_info["at"],
            )
            self._flows[key] = flow
            self.stats["flows_opened"] += 1

        side = flow.forward if is_forward else flow.backward
        side.add(
            size=packet_info["size"],
            payload=packet_info.get("payload", 0),
            at=packet_info["at"],
            ttl=packet_info.get("ttl"),
            flags=packet_info.get("flags", 0),
        )
        self.stats["packets"] += 1

    def collect_expired(self, now: float | None = None) -> list[Flow]:
        """Removes and returns every flow that has closed."""
        moment = now if now is not None else time.time()
        done = [f for f in self._flows.values()
                if (moment - f.last_seen) >= self.idle_seconds
                or (moment - f.started_at) >= self.timeout_seconds]
        for flow in done:
            del self._flows[flow.key]
        self.stats["flows_closed"] += len(done)
        return done

    def flush(self) -> list[Flow]:
        """Closes everything still open — for shutdown, or the end of a pcap."""
        done = list(self._flows.values())
        self._flows.clear()
        self.stats["flows_closed"] += len(done)
        return done

    @property
    def open_flows(self) -> int:
        return len(self._flows)
