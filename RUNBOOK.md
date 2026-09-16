# Operations runbook

What to do when this system is running somewhere that matters, and what has to
be settled by people rather than by code.

Read [DEPLOYMENT.md](DEPLOYMENT.md) first if you are deciding whether to deploy
at all. This document assumes that decision has been made.

---

## 1. Daily

| When | What | Command |
|---|---|---|
| Every morning | Check the box is up and scoring | `curl -fsS http://HOST:8000/api/v1/health` |
| Every morning | Any device still quarantined overnight? | Devices page, filter `quarantined` |
| Every morning | Alerts left unacknowledged | Alerts page, status `new` |
| Nightly (cron) | Backup | `python -m workers.backup create` |
| Weekly (cron) | Retention sweep | `python -m workers.retention` |
| Weekly | Restore a backup into a scratch database and open it | see §5 |

A backup nobody has ever restored is a hope, not a backup. The weekly restore
test is the only thing that turns it into one.

---

## 2. On-call

**This has to be answered before deployment, not after the first 2am alert.**

| Question | Who |
|---|---|
| Who is paged for a `critical` alert out of hours? | _fill in_ |
| Who can quarantine a device? | _fill in_ — needs `devices.quarantine` |
| Who decides a life-critical device may be isolated? | _fill in_ — this is a clinical call, not an IT one |
| Who does biomed escalate to at night? | _fill in_ |
| Who owns this system after the project team leaves? | _fill in_ |

If the last row is blank, do not deploy. An unowned security appliance decays
into an unowned attack surface.

**Out of the box, nothing pages anyone.** Only the `websocket` notification
channel delivers — that is, the alert appears on a screen someone has open.
Email/SMS/Telegram rows are recorded but stay `pending` until an outbound
gateway is configured. Somebody watching a dashboard is not an on-call rota.

---

## 3. When an alert comes in

1. **Open the alert.** Read the description — it says which stage fired and why.
2. **Press "Explain this verdict".** SHAP shows which flow features drove it. If
   nothing in the top features looks like an attack, treat it as suspect.
3. **Check the device.** Devices → the device → vitals chart. If the reported
   line and the forecast line separate, the readings themselves are in question.
4. **Confirm clinically before anything else.** For a `data_integrity` verdict
   the first recommendation is always to check the patient at the bedside. Do
   that before touching the network.
5. **Only then consider a mitigation.**

### Before isolating anything

- **Is it life-critical?** The system will refuse without an explicit
  confirmation. That refusal is the point. Do not click through it because the
  dialog is in the way.
- **Is a patient on it right now?** Patients → the patient shows the assignment.
- **Have you told the nurse in charge?** Cutting a monitor off the network stops
  the central station seeing that patient.

### If you isolate the wrong device

Press **Undo** on the alert. It releases the quarantine and lifts the blocks
immediately, and needs no confirmation — putting a device back is the safe
direction.

If the console is unreachable, do it in the database:

```sql
UPDATE devices SET status='online', quarantined_until=NULL WHERE device_uid='MON-ICU1-001';
UPDATE blocklist SET is_active=0 WHERE value='192.168.20.11';
```

**Quarantines expire on their own after 4 hours and blocks after 24.** A device
cut off during a night shift comes back by itself. That is deliberate: the
failure mode of a forgotten quarantine is worse than the failure mode of an
attacker getting four more hours.

---

## 4. Failure modes

| Symptom | Likely cause | What to do |
|---|---|---|
| No detections appearing | Sniffer stopped, or the mirror port was reconfigured | `ps`/Task Manager for `workers.sniffer`; check the switch's SPAN config |
| Everything alerts | Models not calibrated to this site | §6 — stop showing alerts to clinical staff until recalibrated |
| API returns 503 on `/detect` | No active Stage 1 model | Models page → activate one |
| Backlog growing, alerts arriving late | Traffic exceeds what the box can score | `python -m workers.benchmark` and compare; one box per ward |
| Disk filling | Retention not running | `python -m workers.retention --dry-run`, then without the flag |
| MySQL refusing connections | Disk full, or connection limit | Free space first; the database is the only irreplaceable part |
| Live Monitor blank but detections exist | WebSocket not connected | `GET /api/v1/notifications/live/status`; check the nginx `ws: true` proxy |
| Everything down | The box died | **Patient care is unaffected** — it was never in the traffic path. Restore per §5 when convenient. |

The last row is the one to internalise. This appliance sits on a mirror port. It
can fail completely without touching a single packet a ventilator sends.

---

## 5. Backup and restore

```bash
# nightly
cd backend && ./venv/bin/python -m workers.backup create

# check a dump is real before you need it
./venv/bin/python -m workers.backup verify ../backups/iomt-20260906-020000.sql.gz

# restore (OVERWRITES the current database — it asks you to type the db name)
./venv/bin/python -m workers.backup restore ../backups/iomt-20260906-020000.sql.gz
```

What is irreplaceable, in order:

1. **`alerts`, `alert_actions`, `audit_logs`** — the incident record. Who was
   told what, who did what, when. Not reconstructable from anywhere.
2. **`reports`** — frozen summaries somebody generated on purpose.
3. **`users`, `devices`, `patients`** — the registry. Painful to rebuild.
4. Detections, flows, vitals — high volume, low value once the window has
   passed. These are what retention prunes.

Models and code come from the repository. The database does not.

---

## 6. Calibration — before clinical staff see any alert

The shipped models learned "normal" from a US university testbed. On a synthetic
capture of ordinary MQTT monitor traffic they produced **9 alerts from 9 flows,
six of which were deliberately benign**, with Stage 1 at p ≈ 0.50 — a coin flip.

That is what uncalibrated deployment looks like, and it is how an IDS gets
switched off in week two.

```bash
# 1. Capture a quiet period at the site — several days, no alerts shown to anyone
cd backend && sudo ./venv/bin/python -m workers.sniffer --interface eth0

# 2. Move the thresholds onto that baseline
cd ml && ../backend/venv/bin/python calibrate_site.py \
    --baseline site_baseline.csv --site "Ward ICU-1" --fp-budget 1.0

# 3. Apply the printed thresholds to the ml_models rows, then run in shadow mode
#    — alerts visible to IT only — for a week and measure the real FP rate.
```

**The baseline must be a period the site confirms was quiet.** No script can
check that. If an attack was live during the capture, it is now calibrated in as
normal and the system is blind to it.

---

## 7. Security

- `JWT_SECRET_KEY` — the app refuses to start with the default when `ENV` is
  anything but `development`. Generate one:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- **TLS** — tokens and patient-linked data travel over this. Terminate TLS at
  nginx with a real certificate before it leaves a lab.
- **Database password** — not the default, and not the same as anything else.
- **Roles** — a clinician does not need `devices.quarantine`. Give the narrowest
  role that lets someone do their job.
- **Backups contain patient-linked data.** They are in `.gitignore` for a
  reason; treat the files as you would the database.

---

## 8. What this system is not

State this in writing to anyone who will use it:

- **Not a medical device.** Not validated for clinical decisions. Every reading
  it displays must be confirmed at the bedside before it is acted on.
- **Not a replacement for the firewall, segmentation, or patching.** It detects;
  it does not prevent.
- **Not certified.** Whether it falls under CDSCO's scope is a legal question
  for the hospital's compliance team, not one this project can answer.

---

## 9. Data protection (DPDP Act 2023) — support, not compliance

The system helps with, but does not deliver, compliance. Compliance is the
hospital's obligation.

**What is built in:**

| | |
|---|---|
| Minimisation | No patient names anywhere. Only `patient_code`, age band, sex, ward. |
| Retention | Enforced windows — vitals 30d, detections 90d, audit 365d. `workers/retention.py` |
| Access control | Role-based; every privileged action carries the actor's id |
| Auditability | `audit_logs` records who exported what, and when |
| Purpose limitation | Alerts and reports outlive the raw telemetry they came from |

**What is not, and has to be arranged by the hospital:**

- Notice and consent for processing patient-linked telemetry
- A named Data Protection Officer / data fiduciary
- A breach-notification process (the audit log supports one; it is not one)
- A documented lawful basis for the processing
- Answering a data-principal request — there is no "erase this patient" endpoint

**NABH** likewise needs a documented incident-response SOP with named roles. §2
and §3 of this runbook are a starting point for that SOP; they are not the SOP.
