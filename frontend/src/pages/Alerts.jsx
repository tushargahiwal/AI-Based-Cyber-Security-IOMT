import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useApi from '../hooks/useApi'
import { listAlerts, ALERT_STATUSES, ALERT_SEVERITIES } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import SelectField from '../components/SelectField'
import { BellIcon } from '../components/icons'

const PAGE_SIZE = 20

const STATUS_STYLES = {
  new: 'bg-red-50 text-red-700 ring-red-200',
  acknowledged: 'bg-amber-50 text-amber-700 ring-amber-200',
  investigating: 'bg-sky-50 text-sky-700 ring-sky-200',
  resolved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  false_positive: 'bg-slate-100 text-slate-600 ring-slate-200',
}

const SEVERITY_STYLES = {
  info: 'text-slate-600',
  low: 'text-sky-700',
  medium: 'text-amber-700',
  high: 'text-orange-700',
  critical: 'text-red-700',
}

export default function Alerts() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [severity, setSeverity] = useState('')

  const { data, loading, error } = useApi(
    () => listAlerts({ page, size: PAGE_SIZE, status: status || undefined, severity: severity || undefined }),
    [page, status, severity]
  )

  const items = data?.items || []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <SelectField value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} className="min-w-[10rem]">
          <option value="" className="bg-white">All statuses</option>
          {ALERT_STATUSES.map((s) => <option key={s} value={s} className="bg-white">{s.replace(/_/g, ' ')}</option>)}
        </SelectField>
        <SelectField value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1) }} className="min-w-[9rem]">
          <option value="" className="bg-white">All severities</option>
          {ALERT_SEVERITIES.map((s) => <option key={s} value={s} className="bg-white capitalize">{s}</option>)}
        </SelectField>
      </div>

      <ErrorBanner error={error} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Risk</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Alert</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Severity</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Occurrences</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Last seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-500">
                    No alerts.
                  </td>
                </tr>
              )}
              {items.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => navigate(`/alerts/${a.id}`)}
                  className="cursor-pointer transition-colors hover:bg-slate-100"
                >
                  <td className="px-5 py-3.5">
                    <span className="font-mono text-sm font-semibold text-slate-800">
                      {a.risk_score != null ? a.risk_score.toFixed(0) : '—'}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-700">
                        <BellIcon className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-800">{a.title}</p>
                        <p className="font-mono text-[11px] text-slate-500">{a.alert_uid}{a.device_uid ? ` · ${a.device_uid}` : ''}</p>
                      </div>
                    </div>
                  </td>
                  <td className={`px-5 py-3.5 capitalize ${SEVERITY_STYLES[a.severity] || 'text-slate-600'}`}>
                    {a.severity}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs capitalize ring-1 ring-inset ${STATUS_STYLES[a.status] || ''}`}
                    >
                      {a.status.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">{a.occurrence_count}</td>
                  <td className="px-5 py-3.5 text-slate-600">
                    {a.last_seen_at ? new Date(a.last_seen_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {total > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3.5 text-xs text-slate-500">
            <span>
              {total} alert{total === 1 ? '' : 's'} · page {page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-slate-700 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-slate-700 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
