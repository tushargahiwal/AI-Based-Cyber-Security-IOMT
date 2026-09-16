"""Out-of-band enforcement — stopping an attack without carrying the traffic.

The whole system sits on a mirror port precisely so that it cannot break the
network. Prevention must not throw that away. An inline IPS in front of a
ventilator means that when the IPS hangs, the ventilator's telemetry stops, and
we would have built a patient-safety hazard in order to prevent one.

So nothing here forwards or drops a packet. Every actuator instructs
infrastructure that is already in the path — the switch, the firewall, the MQTT
broker — or puts a correct ARP binding back on the wire. If this process dies
mid-action the network keeps running exactly as it was.

Three rules every actuator inherits and cannot opt out of:

  1. **Dry run until switched on, per actuator.** A new deployment computes what
     it would do and logs it. Turning enforcement live is a deliberate act by a
     named person, per actuator, not a default.
  2. **A global kill switch.** One flag stops all enforcement instantly, without
     a restart and without editing anything.
  3. **Nothing is done to a life-critical device automatically.** Ever. The
     caller decides that, and `EnforcementPlan` refuses to carry it silently.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class EnforcementResult:
    """What an actuator did, or would have done."""

    actuator: str
    target: str
    succeeded: bool
    dry_run: bool
    detail: str
    at: datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        prefix = "would " if self.dry_run else ""
        outcome = "" if self.succeeded else " (FAILED)"
        return f"{prefix}{self.detail}{outcome}"


class Actuator(ABC):
    """Something that can act on the network on our behalf.

    Subclasses implement `_act`; they never decide *whether* they are allowed to.
    That decision belongs to enforcement_service, which knows about life-critical
    devices and the kill switch, and it is kept out of here so a new actuator
    cannot accidentally ship without those checks.
    """

    #: Stable identifier, used in config keys and in the audit trail.
    name: str = "actuator"

    #: What this actuator needs before it can do anything real.
    requires: tuple[str, ...] = ()

    def __init__(self, config: dict | None = None, *, dry_run: bool = True):
        self.config = config or {}
        self.dry_run = dry_run

    def available(self) -> tuple[bool, str]:
        """Whether this actuator is configured enough to be used."""
        missing = [key for key in self.requires if not self.config.get(key)]
        if missing:
            return False, f"not configured: {', '.join(missing)}"
        return True, "configured"

    def execute(self, *, target: str, reason: str, **kwargs) -> EnforcementResult:
        ready, why = self.available()
        if not ready:
            return EnforcementResult(self.name, target, False, self.dry_run,
                                     f"{self.name} unavailable — {why}")

        if self.dry_run:
            return EnforcementResult(self.name, target, True, True,
                                     self.describe(target=target, **kwargs))

        try:
            detail = self._act(target=target, reason=reason, **kwargs)
            logger.info("enforcement: %s -> %s (%s)", self.name, target, detail)
            return EnforcementResult(self.name, target, True, False, detail)
        except Exception as exc:
            # A failed enforcement must surface, not vanish. The alert stays open
            # and the analyst sees that the action did not take.
            logger.warning("enforcement failed: %s -> %s", self.name, target, exc_info=True)
            return EnforcementResult(self.name, target, False, False,
                                     f"{type(exc).__name__}: {exc}")

    @abstractmethod
    def describe(self, *, target: str, **kwargs) -> str:
        """What this would do, in words, without doing it."""

    @abstractmethod
    def _act(self, *, target: str, reason: str, **kwargs) -> str:
        """Do it. Returns a description of what happened."""
