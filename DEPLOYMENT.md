# Deployment readiness

Short version: **this is not ready for a live hospital, and the blockers are
mostly not technical.** This document says exactly what is done, what is not,
and what the honest path looks like.

---

## Where it stands

| | |
|---|---|
| ✅ Ready for | demonstration, viva, a lab testbed, a supervised passive pilot |
| ❌ Not ready for | live clinical use with mitigation enabled |

---

## Built

| Gap | Status |
|---|---|
| Packet capture | ✅ `workers/sniffer.py` + `flow_assembler.py` + `feature_extractor.py` |
| Undo a mitigation | ✅ one click, no confirmation — the safe direction never needs one |
| Time-limited quarantine | ✅ 4 h, blocks 24 h, swept every minute |
| Expiry actually enforced | ✅ `expires_at` was written and never read — fixed |
| Default JWT secret | ✅ the app refuses to start with it outside development |
| Retention / pruning | ✅ `workers/retention.py`, windows in `config.py` |
| Backup / restore | ✅ `workers/backup.py`, with a verify step |
| Load testing | ✅ `workers/benchmark.py` — **~18 flows/sec at p99** on a dev laptop |
| Site calibration | ✅ `ml/calibrate_site.py` |
| Clinical disclaimer | ✅ in the console, permanently visible |
| Docker | 🟡 written, `docker compose config` validates, **never built or run** |

## Not built

| Gap | Why it matters |
|---|---|
| **Models calibrated to a real site** | The blocker. See below. |
| TLS | Tokens and patient-linked data travel in the clear |
| High availability | One box, no failover. Acceptable on a mirror port; state it anyway |
| Failure-mode testing | Disk full, DB down, sniffer wedged — untested |
| Cross-dataset validation | Needs a second dataset (CICIoMT2024) |
| An on-call rota | Not a code problem |

---

## The measurement that decides everything

Running the shipped models over a synthetic capture of ordinary MQTT monitor
traffic — six deliberately normal conversations and three from a spoofed MAC:

```
packets=324 flows=9 scored=9 alerts=9 errors=0
verdicts: zero_day_suspect=9
```

**Nine alerts from nine flows.** Six of them benign. Stage 1 sat at p ≈ 0.50 —
it had no opinion at all.

Nothing is broken. The models learned "normal" from WUSTL-EHMS-2020: one
monitor, one server, a university lab. An ICU is thirty devices from five
vendors with rounds, shift changes and Wi-Fi congestion. Their normal is not our
normal.

Deployed as-is this alerts on everything, and the staff switch it off inside a
week. That is the single most common way an IDS deployment fails, and it is
worth more in a report than a good accuracy number.

The one encouraging detail in that run: the MAC/IP binding check caught the
spoofed host, using the device registry rather than anything learned from the
dataset. That check works on day one because it compares against what biomed
entered at onboarding — no calibration needed.

---

## Path to a real deployment

| Phase | What | Gate to the next phase |
|---|---|---|
| **1. Capture** ✅ | `workers/sniffer.py` on a mirror port | Flows assembling correctly |
| **2. Passive pilot** | 3–4 weeks recording. **No alerts to anyone.** | A baseline the site confirms was quiet |
| **3. Calibrate** | `ml/calibrate_site.py` on that baseline | Thresholds moved onto site traffic |
| **4. Shadow mode** | Alerts to IT only, for a month | False-positive rate the site will accept |
| **5. Supervised** | Clinical staff see alerts, **mitigation disabled** | Ethics + legal clearance |
| **6. Full** | Mitigation enabled, life-critical still gated | — |

**Phase 2 cannot be skipped.** Without it nobody knows whether this works on
that network, and the evidence above says it will not, initially.

---

## Before any of that — the legal questions

None of these are engineering problems, and none can be answered here.

| | |
|---|---|
| **CDSCO** | The system displays vitals and can act on devices attached to patients. Whether that puts it in scope as a medical device is a question for the hospital's regulatory/legal team. |
| **DPDP Act 2023** | Notice, consent, lawful basis, a named data fiduciary, a breach process. The system supports these (§9 of the runbook); it does not deliver them. |
| **NABH** | A documented incident-response SOP with named roles. |
| **Ethics** | A student project touching data from live patients needs institutional ethics approval. |
| **Liability** | If it misses an attack and a patient is harmed — whose responsibility, and under what agreement? |

---

## What to say in the report

> We built and validated the detection engine, the console and the capture path,
> and measured throughput and detection performance on a labelled dataset. We
> also measured what happens when the shipped models meet traffic they were not
> trained on: nine alerts from nine flows, six of them benign. That result is why
> our deployment plan begins with a passive baseline-capture phase and
> site-specific calibration rather than with installation. We deliberately did
> not deploy in a clinical environment: an uncalibrated detector produces alert
> fatigue, and alert fatigue in an ICU is a patient-safety risk, not an
> inconvenience.

That answers "can this go in a hospital?" better than "yes" does.
