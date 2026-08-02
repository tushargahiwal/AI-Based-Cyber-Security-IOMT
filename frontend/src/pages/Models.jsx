import { useState } from 'react'
import useApi from '../hooks/useApi'
import { listModels, getModelMetrics, activateModel, retrainModel } from '../api/client'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'

const STAGE_LABELS = {
  1: 'Stage 1 · Binary detector',
  2: 'Stage 2 · Multi-class classifier',
  3: 'Stage 3 · Zero-day / anomaly',
  4: 'Stage 4 · Vitals plausibility',
  5: 'Stage 5 · Explainability',
}

export default function Models() {
  const models = useApi(listModels, [])
  const rows = models.data?.items || models.data || []
  const [selectedId, setSelectedId] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const activate = async (id) => {
    setBusyId(id)
    try {
      await activateModel(id)
      models.reload()
    } finally {
      setBusyId(null)
    }
  }

  const retrain = async (id) => {
    setBusyId(id)
    try {
      await retrainModel({ model_id: id })
      models.reload()
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Models</h1>
        <p className="text-sm text-slate-500">Registry of every model backing the five-stage detection pipeline.</p>
      </div>

      <Card>
        <ErrorBanner error={models.error} label="model registry" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-4">Model</th>
                <th className="pb-2 pr-4">Stage</th>
                <th className="pb-2 pr-4">Algorithm</th>
                <th className="pb-2 pr-4">Version</th>
                <th className="pb-2 pr-4">Active</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {rows.length === 0 && !models.loading && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No models registered yet — run the training pipeline and register artifacts in{' '}
                    <code className="text-slate-400">ml_models</code>.
                  </td>
                </tr>
              )}
              {rows.map((m) => (
                <tr key={m.id} className="text-slate-300">
                  <td className="py-2 pr-4">
                    <button
                      onClick={() => setSelectedId(m.id)}
                      className="font-medium text-slate-200 hover:text-sky-300"
                    >
                      {m.display_name || m.model_code}
                    </button>
                  </td>
                  <td className="py-2 pr-4 text-slate-400">{STAGE_LABELS[m.stage] || `Stage ${m.stage}`}</td>
                  <td className="py-2 pr-4 text-slate-400">{m.algorithm}</td>
                  <td className="py-2 pr-4 text-slate-400">{m.version}</td>
                  <td className="py-2 pr-4">
                    {m.is_active ? (
                      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300 ring-1 ring-inset ring-emerald-500/30">
                        active
                      </span>
                    ) : (
                      <span className="text-xs text-slate-500">inactive</span>
                    )}
                  </td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <button
                        disabled={busyId === m.id || m.is_active}
                        onClick={() => activate(m.id)}
                        className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-300 hover:bg-white/10 disabled:opacity-40"
                      >
                        Activate
                      </button>
                      <button
                        disabled={busyId === m.id}
                        onClick={() => retrain(m.id)}
                        className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-300 hover:bg-white/10 disabled:opacity-40"
                      >
                        Retrain
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {selectedId && <ModelMetricsPanel modelId={selectedId} onClose={() => setSelectedId(null)} />}
    </div>
  )
}

function ModelMetricsPanel({ modelId, onClose }) {
  const metrics = useApi(() => getModelMetrics(modelId), [modelId])
  const rows = metrics.data?.items || metrics.data || []

  return (
    <Card
      title="Metrics"
      action={
        <button onClick={onClose} className="text-xs text-slate-500 hover:text-slate-300">
          Close
        </button>
      }
    >
      <ErrorBanner error={metrics.error} label="model metrics" />
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase tracking-wide text-slate-500">
              <th className="pb-2 pr-4">Split</th>
              <th className="pb-2 pr-4">Class</th>
              <th className="pb-2 pr-4">Precision</th>
              <th className="pb-2 pr-4">Recall</th>
              <th className="pb-2 pr-4">F1</th>
              <th className="pb-2">ROC-AUC</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.length === 0 && !metrics.loading && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-slate-500">
                  No metrics recorded for this model yet.
                </td>
              </tr>
            )}
            {rows.map((r, i) => (
              <tr key={i} className="text-slate-300">
                <td className="py-2 pr-4 text-slate-400">{r.split}</td>
                <td className="py-2 pr-4">{r.class_label}</td>
                <td className="py-2 pr-4">{fmtPct(r.precision)}</td>
                <td className="py-2 pr-4">{fmtPct(r.recall)}</td>
                <td className="py-2 pr-4">{fmtPct(r.f1_score)}</td>
                <td className="py-2">{fmtPct(r.roc_auc)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function fmtPct(v) {
  if (v === undefined || v === null) return '—'
  return `${(v * 100).toFixed(1)}%`
}
