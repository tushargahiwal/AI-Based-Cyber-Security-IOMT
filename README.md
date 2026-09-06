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
