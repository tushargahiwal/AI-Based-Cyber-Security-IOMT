# AI-Based-Cyber-Security-IOMT
We build a network-edge IDS appliance (software, runs on a laptop / Raspberry Pi / VM sitting beside the hospital gateway). It passively captures traffic to and from IoMT devices, converts packets into statistical flow records, and pushes each flow through a five-stage detection pipeline.

## Running a detection stream

There is no capture card here, so `backend/workers/replay.py` stands in for the
sniffer: it walks `data/raw/wustl-ehms-2020.csv` in its original capture order
and pushes every row through the same code path a live flow would take — the
vitals stream into Stage 4, the flow features into Stages 1-3.

```
cd backend
./venv/Scripts/python.exe -m workers.replay --limit 200 --speed 5
./venv/Scripts/python.exe -m workers.replay --device VENT-ICU1-003 --start 230 --limit 60
./venv/Scripts/python.exe -m workers.replay --attacks-only --limit 50 --speed 2
./venv/Scripts/python.exe -m workers.replay --limit 100 --dry-run   # writes nothing
```

`--speed` is rows per second (`0` for as fast as the models will go). Rows are
sent to one device at a time in blocks, because Stage 4 needs 31 consecutive
readings from the same device before it can score anything.

## Watching it work

Two ways to drive traffic through the pipeline:

- **Attack Simulator** (`/simulator` in the UI) — pick benign, attack, or the
  boundary between them, then watch the verdicts land on **Live Monitor**
  (`/live`), which subscribes to a WebSocket at `/api/v1/ws`.
- **`workers.replay`** on the command line, for longer or scripted runs.

Both push real rows from the labelled capture through the real models. Nothing
in either view is scripted.

## Tests

```
cd backend && ./venv/Scripts/python.exe -m pytest tests -q
```

The suite covers the decision table, the doc §14.3 safety rules, and the
contracts between the trained artifacts and the code that serves them. It needs
the model files but not a database.

## Running it with Docker

```
docker compose up --build
```

Then open http://localhost:8080. The database is created from `database/schema.sql`
and seeded on first start. `models/` and `data/` are mounted from the repository
rather than baked into the image, so retraining a model does not mean rebuilding
anything. Override `JWT_SECRET_KEY` before showing the deployment to anyone —
tokens signed with the default are tokens anyone can forge.

## Models

Eleven models, per doc §8. Train them in this order (later ones load earlier
artifacts), then load the measured numbers into the registry:

```
cd ml
../backend/venv/Scripts/python.exe preprocessing.py       # splits, scaler, feature order
../backend/venv/Scripts/python.exe train_binary.py        # M1 RF, M8 LogReg, M9 SVM-RBF
../backend/venv/Scripts/python.exe train_multiclass.py    # M2 XGBoost (Stage 2)
../backend/venv/Scripts/python.exe train_autoencoder.py   # M4 (Stage 3)
../backend/venv/Scripts/python.exe train_vitals_lstm.py   # M6 (Stage 4)
../backend/venv/Scripts/python.exe train_novelty.py       # M5 iForest, M7 One-Class SVM
../backend/venv/Scripts/python.exe train_cnn_bilstm.py    # M3 sequence model
../backend/venv/Scripts/python.exe train_stacking.py      # M10 meta-learner

cd ../backend && ./venv/Scripts/python.exe register_models.py
```

`register_models.py` reads `models/*.json` and fills `ml_models`, `training_runs`,
`model_metrics` and `feature_importances`, which is what the Models page reads.

## Experiments

```
cd ml
../backend/venv/Scripts/python.exe experiment_zero_day.py   # §9.3
../backend/venv/Scripts/python.exe experiment_ablation.py   # §9.5
```

**Zero-day (§9.3)** removes one attack family from training entirely and asks
what still catches it. This is the experiment the architecture stands on:

| Held-out family | M1 RF | M2 XGB | M5 iForest | M7 One-Class SVM |
|---|---|---|---|---|
| Data Alteration | 0.00% | 0.00% | 100.00% | 100.00% |
| Spoofing | 0.00% | 0.00% | 0.65% | 19.48% |

The supervised models catch nothing they were not trained on. Stage 3, which
never sees attack data at all, catches every Data Alteration flow.

**Ablation (§9.5)** measures whether the §7.2 engineered features earn their
place. Five of the ten are computable from this capture; the rest need payload
bytes, TTL, MQTT control types or timestamps that WUSTL does not carry, and are
declared unavailable rather than zero-filled.

The experiment also carries a leak guard, and it found one:
`arp_binding_violation` reproduces the WUSTL label *exactly*, because the capture
was produced with one attacker host using a fixed MAC. Any model given that
column scores 100% and has learned the attacker's network card. It is detected
and dropped automatically — see `ml/engineered_features.py`.

## Live capture (Module 2)

```
cd backend
sudo ./venv/bin/python -m workers.sniffer --interface eth0     # live, needs root
./venv/Scripts/python.exe -m workers.sniffer --pcap capture.pcap --dry-run
```

Assembles packets into bidirectional flows, builds the model's feature vector,
and scores each closed flow through the same pipeline the API uses. Runs on a
**mirror/SPAN port, never inline** — if it crashes, traffic to the ventilator is
unaffected, because it never carried that traffic.

32 of the 44 features come from packets, 8 from the vitals stream, and 4 (packet
loss) are not measurable without TCP stream reassembly and are reported as
absent rather than as zero.

## Operations

```
python -m workers.retention --dry-run    # what the retention windows would delete
python -m workers.backup create          # nightly dump, with a verify step
python -m workers.benchmark --flows 200  # how much traffic this box can score
```

`workers/backup.py` and `workers/retention.py` are what make the incident record
survivable and the data-retention window enforced rather than aspirational.

## Before deploying anywhere real

Read **[DEPLOYMENT.md](DEPLOYMENT.md)** — what is ready, what is not, and the
phased path. Then **[RUNBOOK.md](RUNBOOK.md)** for on-call, failure modes and
the compliance questions that are the hospital's to answer.

Short version: this is ready for a demo, a lab, or a supervised passive pilot.
It is **not** ready for live clinical use, and the calibration evidence in
DEPLOYMENT.md explains why in one measurement.

## Prevention (enforcement)

Detection alone leaves the attack running. Enforcement stops it — **out-of-band**,
so the appliance still never carries a packet. It instructs infrastructure that
is already in the path, or puts a correct ARP binding back on the wire.

| Actuator | What it does | Why it is safe |
|---|---|---|
| `arp_heal` | Broadcasts the registered MAC/IP binding | Reverses ARP spoofing without disconnecting anything |
| `switch_port` | Shuts or re-VLANs the **attacker's** access port | The medical device stays exactly where it is |
| `firewall` | Blocks the attacker upstream | A rule on kit already in the path |
| `mqtt_revoke` | Stops a cloned client publishing | Surgical — no network change at all |

`switch_port` and `firewall` run **your own command**, held in `system_config`.
Every hospital's switch is different, and shipping an untested driver for each
would mean shipping several that report success and do nothing.

### The decision that matters

**Who gets blocked is the dangerous question, not what.** For a
man-in-the-middle the monitor is the *victim*: cutting it off does not stop the
attacker, removes the patient from the central station, and leaves the attacker
on the network — three failures from one click.

So targets are chosen by role, never by direction:

| Endpoint | Treatment |
|---|---|
| Registered medical device | Never acted on without explicit confirmation. Life-critical: stronger refusal, and the advice is to isolate the ward segment instead. |
| Protected infrastructure (HIS, PACS, gateway — `enforcement.protected_hosts`) | Never blocked. Taking out the HIS is a bigger incident than most alerts. |
| Everything else | The adversary. Actionable. |
| Both ends known | No target is named, and the plan says why. |

### Safety controls

- **Dry run by default, per actuator.** A new deployment logs what it *would* do.
- **A global kill switch** (`enforcement.enabled`), read on every action — one
  call stops everything, no restart.
- **Reversible and time-limited** — quarantines lift after 4 h, blocks after 24.
- **Targets are validated** before reaching a command line. They come from
  packets, so they are attacker-controlled; `shell=False`, and a target that
  looks like an option is refused.
- **Every action is audited** with the actuator, the target, and the reasoning
  about who the adversary was.

```
GET  /api/v1/enforcement/status                    what is live vs rehearsing
GET  /api/v1/enforcement/alerts/{id}/plan          what would be done, and to whom
POST /api/v1/enforcement/alerts/{id}/execute       carry out one action
POST /api/v1/enforcement/kill-switch               stop everything, now
```
