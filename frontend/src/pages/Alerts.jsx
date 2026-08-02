import { useState } from 'react'
import useApi from '../hooks/useApi'
import {
  listAlerts,
  getAlert,
  acknowledgeAlert,
  resolveAlert,
  markFalsePositive,
} from '../api/client'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import SeverityBadge from '../components/SeverityBadge'
import VerdictBadge from '../components/VerdictBadge'

const STATUS_OPTIONS = ['new', 'acknowledged', 'investigating', 'resolved', 'false_positive']
const SEVERITY_OPTIONS = ['info', 'low', 'medium', 'high', 'critical']

export default function Alerts() {
  const [filters, setFilters] = useState({ status: '', severity: '' })
  const [selectedId, setSelectedId] = useState(null)

  const alerts = useApi(() => listAlerts(cleanParams(filters)), [filters.status, filters.severity])
  const rows = alerts.data?.items || alerts.data || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Alerts Console</h1>
        <p className="text-sm text-slate-500">Triage, acknowledge and resolve detections that need a human.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Select
          label="Status"
          value={filters.status}
          onChange={(v) => setFilters((f) => ({ ...f, status: v }))}
          options={STATUS_OPTIONS}
        />
        <Select
          label="Severity"
          value={filters.severity}
          onChange={(v) => setFilters((f) => ({ ...f, severity: v }))}
          options={SEVERITY_OPTIONS}
        />
      </div>

      <Card>
        <ErrorBanner error={alerts.error} label="alerts" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-4">Alert</th>
                <th className="pb-2 pr-4">Device</th>
                <th className="pb-2 pr-4">Verdict</th>
                <th className="pb-2 pr-4">Severity</th>
                <th className="pb-2 pr-4">Risk</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2">First seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {rows.length === 0 && !alerts.loading && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    No alerts match these filters.
                  </td>
                </tr>
              )}
              {rows.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => setSelectedId(a.id)}
                  className="cursor-pointer text-slate-300 hover:bg-white/5"
                >
                  <td className="py-2 pr-4">
                    <p className="font-medium text-slate-200">{a.title}</p>
                    <p className="text-xs text-slate-500">{a.alert_uid}</p>
                  </td>
                  <td className="py-2 pr-4 text-slate-400">{a.device_id ?? '—'}</td>
                  <td className="py-2 pr-4">
                    <VerdictBadge verdict={a.attack_type?.family?.toLowerCase() || 'known_attack'} />
                  </td>
                  <td className="py-2 pr-4">
                    <SeverityBadge severity={a.severity} />
                  </td>
                  <td className="py-2 pr-4 text-slate-400">{a.risk_score ?? '—'}</td>
                  <td className="py-2 pr-4 text-slate-400">{a.status}</td>
                  <td className="py-2 text-slate-500">{formatTime(a.first_seen_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {selectedId && (
        <AlertDrawer alertId={selectedId} onClose={() => setSelectedId(null)} onChanged={alerts.reload} />
      )}
    </div>
  )
}

function AlertDrawer({ alertId, onClose, onChanged }) {
  const detail = useApi(() => getAlert(alertId), [alertId])
  const a = detail.data || {}
  const [busy, setBusy] = useState(false)

  const runAction = async (fn) => {
    setBusy(true)
    try {
      await fn(alertId)
      onChanged?.()
      detail.reload()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/50" onClick={onClose}>
      <div
        className="h-full w-full max-w-lg overflow-y-auto border-l border-white/10 bg-[#0d1017] p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-100">{a.title || `Alert #${alertId}`}</h2>
            <p className="text-xs text-slate-500">{a.alert_uid}</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
            ✕
          </button>
        </div>

        <ErrorBanner error={detail.error} label="alert detail" />

        {!detail.loading && !detail.error && (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-2">
              {a.severity && <SeverityBadge severity={a.severity} />}
              {a.status && (
                <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-xs text-slate-300 ring-1 ring-inset ring-white/10">
                  {a.status}
                </span>
              )}
              {a.risk_score != null && (
                <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-xs text-slate-300 ring-1 ring-inset ring-white/10">
                  risk {a.risk_score}
                </span>
              )}
            </div>

            <p className="text-sm text-slate-400">{a.description || 'No description provided.'}</p>

            {a.explanation && (
              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Why the system decided this (SHAP)
                </h3>
                <p className="mb-2 text-sm text-slate-300">{a.explanation.narrative}</p>
                <ul className="space-y-1.5">
                  {(a.explanation.top_features || []).map((f, i) => (
                    <li key={i} className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-1.5 text-xs">
                      <span className="text-slate-300">{f.feature}</span>
                      <span className="text-slate-500">
                        {f.value} · normal {f.normal_range || '—'}
                      </span>
                      <span className={f.shap >= 0 ? 'text-red-300' : 'text-emerald-300'}>
                        {f.shap >= 0 ? '+' : ''}
                        {f.shap}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {a.recommendations?.length > 0 && (
              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Recommended action (advisory only)
                </h3>
                <ul className="space-y-1.5 text-sm text-slate-300">
                  {a.recommendations.map((r, i) => (
                    <li key={i} className="rounded-lg bg-white/5 px-3 py-2">
                      {r.recommendation}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="flex flex-wrap gap-2 border-t border-white/10 pt-4">
              <ActionButton disabled={busy} onClick={() => runAction(acknowledgeAlert)}>
                Acknowledge
              </ActionButton>
              <ActionButton disabled={busy} onClick={() => runAction((id) => resolveAlert(id, 'Resolved from console'))}>
                Resolve
              </ActionButton>
              <ActionButton disabled={busy} onClick={() => runAction(markFalsePositive)} variant="ghost">
                Mark false positive
              </ActionButton>
            </section>
          </div>
        )}
      </div>
    </div>
  )
}

function ActionButton({ children, variant = 'solid', ...props }) {
  const styles =
    variant === 'solid'
      ? 'bg-sky-500/15 text-sky-300 ring-1 ring-inset ring-sky-500/30 hover:bg-sky-500/25'
      : 'bg-white/5 text-slate-400 ring-1 ring-inset ring-white/10 hover:bg-white/10'
  return (
    <button
      {...props}
      className={`rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50 ${styles}`}
    >
      {children}
    </button>
  )
}

function Select({ label, value, onChange, options }) {
  return (
    <label className="flex items-center gap-2 text-xs text-slate-400">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-white/10 bg-[#0d1017] px-2 py-1.5 text-xs text-slate-200 focus:border-sky-500/50 focus:outline-none"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  )
}

function cleanParams(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v))
}

function formatTime(t) {
  if (!t) return '—'
  try {
    return new Date(t).toLocaleString()
  } catch {
    return t
  }
}
