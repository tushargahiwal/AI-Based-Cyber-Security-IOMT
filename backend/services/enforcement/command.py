"""Enforcement by running the operator's own command.

Every hospital's switch and firewall are different — a Cisco stack, an Aruba
controller, pfSense, a Linux gateway with iptables. Shipping a driver for each
would mean shipping several we never tested against real hardware, and an
untested enforcement driver is worse than none: it reports success and does
nothing.

So the actuator is the operator's command line, held in system_config. The
network team writes the one command they already know works on their gear, we
substitute the target into it and run it. What we own is the safety around it:
dry run, the kill switch, the life-critical rule, the audit trail, and the fact
that the command is configuration rather than something a request can supply.

Typical templates:

    switch_port   ssh netadmin@sw1 "interface {port} ; shutdown"
    switch_port   snmpset -v2c -c {community} {switch} ifAdminStatus.{port} i 2
    firewall      ssh fw01 "iptables -I FORWARD -s {target} -j DROP"
    firewall      pfctl -t quarantine -T add {target}

Only `{target}` and keys the operator put in the actuator's own config are
substituted. A value that came from the network — an IP or MAC observed in a
packet — is validated before it reaches a shell, because that is the obvious way
this becomes remote code execution.
"""

import re
import shlex
import subprocess

from .base import Actuator

# What may appear as {target}. An IP, a MAC, or a switch port name — deliberately
# narrow, because this string ends up in a command line.
#
# The leading character may not be a hyphen. shell=False already rules out
# command injection, but a target of "-D" or "--flush" would still be read by the
# target program as an OPTION rather than an address, changing what the command
# does. No real IP, MAC or port name starts with one.
SAFE_TARGET = re.compile(r"^[A-Za-z0-9._:/][A-Za-z0-9._:/-]{0,63}$")

DEFAULT_TIMEOUT_SECONDS = 20


class CommandActuator(Actuator):
    """Runs a configured command template with the target substituted in."""

    name = "command"
    requires = ("template",)

    def _render(self, target: str) -> list[str]:
        if not SAFE_TARGET.match(target):
            raise ValueError(
                f"refusing to put {target!r} in a command line — it is not a plain "
                "IP, MAC or port name. Values observed on the network are not trusted here."
            )

        template = self.config["template"]
        # Split first, substitute second. Substituting into the string and then
        # splitting would let a target containing a space become extra arguments.
        parts = shlex.split(template)
        substitutions = {k: str(v) for k, v in self.config.items() if k != "template"}
        substitutions["target"] = target

        rendered = []
        for part in parts:
            for key, value in substitutions.items():
                part = part.replace("{" + key + "}", value)
            if "{" in part and "}" in part:
                raise ValueError(f"template placeholder left unfilled in {part!r}")
            rendered.append(part)
        return rendered

    def describe(self, *, target: str, **kwargs) -> str:
        try:
            command = self._render(target)
        except ValueError as exc:
            return f"would refuse: {exc}"
        label = self.config.get("label", self.name)
        return f"run [{label}]: {' '.join(command)}"

    def _act(self, *, target: str, reason: str, **kwargs) -> str:
        command = self._render(target)
        timeout = int(self.config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))

        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            # shell=False is the point: no shell means no shell metacharacters,
            # whatever ends up in the template.
            shell=False,
        )
        output = (result.stdout or result.stderr).decode(errors="replace").strip()
        if result.returncode != 0:
            raise RuntimeError(
                f"exit {result.returncode}: {output[:300] or 'no output'}"
            )
        label = self.config.get("label", self.name)
        return f"[{label}] {' '.join(command)} -> ok{f': {output[:200]}' if output else ''}"


class SwitchPortActuator(CommandActuator):
    """Isolates a host by shutting or re-VLANing its access port.

    This is what actually ends an attack: the attacker's own switch port goes
    down, out-of-band, while every medical device stays exactly where it was.
    """

    name = "switch_port"


class FirewallActuator(CommandActuator):
    """Blocks a host at the firewall that already sits in the path."""

    name = "firewall"
