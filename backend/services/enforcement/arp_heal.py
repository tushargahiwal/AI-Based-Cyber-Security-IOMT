"""Reverses ARP spoofing by putting the true binding back on the wire.

This is the most directly useful actuator we have, because ARP spoofing is how
the man-in-the-middle in our threat model gets between the monitor and the HIS
in the first place.

How the attack works: the attacker broadcasts "192.168.20.11 is at MY MAC". Every
host and the switch believe it, and the monitor's traffic starts flowing through
the attacker, who edits the SpO2 value in transit.

How this reverses it: we broadcast the correct binding — "192.168.20.11 is at
84:3a:4b:0f:5b:94", the MAC biomed recorded at onboarding — as a gratuitous ARP.
Caches relearn the truth and traffic returns to its proper path.

Why this is the right shape of response:

  * Nothing is blocked. The monitor keeps working throughout; the patient never
    disappears from the central station.
  * We are not in the path. This is one broadcast frame, not a forwarding role.
  * It is self-correcting. If the attacker keeps spoofing, they win the next
    round and we send another — so this buys time and visibility rather than
    claiming a permanent fix. Removing the attacker's switch port is what ends
    it, and that is a separate actuator.

The registry is the source of truth for the correct MAC. That is what makes this
safe: we are asserting what biomed recorded, not guessing from traffic.
"""

from .base import Actuator

# One frame is easily lost, and the attacker is likely still broadcasting. A
# short burst wins the cache race without becoming traffic in its own right.
REPEATS = 5
INTERVAL_SECONDS = 0.2


class ArpHealActuator(Actuator):
    name = "arp_heal"
    requires = ("interface",)

    def describe(self, *, target: str, correct_mac: str = "", **kwargs) -> str:
        return (f"broadcast a gratuitous ARP restoring {target} -> {correct_mac} "
                f"({REPEATS} frames on {self.config.get('interface', '?')})")

    def _act(self, *, target: str, reason: str, correct_mac: str = "", **kwargs) -> str:
        if not correct_mac:
            raise ValueError(
                "no registered MAC for this IP — cannot assert a binding we do not know. "
                "Register the device's MAC before relying on ARP healing."
            )

        import time

        from scapy.layers.l2 import ARP, Ether
        from scapy.sendp import sendp

        interface = self.config["interface"]
        # op=2 is an ARP reply. Sent unsolicited to the broadcast address, it is
        # a "gratuitous ARP": every listener updates its cache for this IP.
        frame = Ether(src=correct_mac, dst="ff:ff:ff:ff:ff:ff") / ARP(
            op=2, psrc=target, hwsrc=correct_mac, pdst=target, hwdst="ff:ff:ff:ff:ff:ff"
        )

        for i in range(REPEATS):
            sendp(frame, iface=interface, verbose=False)
            if i < REPEATS - 1:
                time.sleep(INTERVAL_SECONDS)

        return (f"broadcast {REPEATS} gratuitous ARP frames on {interface} restoring "
                f"{target} -> {correct_mac}; caches should relearn the registered binding")
