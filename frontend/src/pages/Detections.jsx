import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useApi from '../hooks/useApi'
import { listDetections, DETECTION_VERDICTS } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import SelectField from '../components/SelectField'
import { ActivityIcon, AlertTriangleIcon } from '../components/icons'

const PAGE_SIZE = 20

const VERDICT_STYLES = {
  benign: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  known_attack: 'bg-red-50 text-red-700 ring-red-200',
  uncertain: 'bg-amber-50 text-amber-700 ring-amber-200',
  zero_day_suspect: 'bg-orange-50 text-orange-700 ring-orange-200',
  data_integrity: 'bg-purple-50 text-purple-700 ring-purple-200',
}

const SEVERITY_STYLES = {
  info: 'text-slate-600',
  low: 'text-sky-700',
  medium: 'text-amber-700',
  high: 'text-orange-700',
  critical: 'text-red-700',
}

export default function Detections() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [verdict, setVerdict] = useState('')

  const { data, loading, error } = useApi(
    () => listDetections({ page, size: PAGE_SIZE, final_verdict: verdict || undefined }),
    [page, verdict]
  )

  const items = data?.items || []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-6">
      <SelectField value={verdict} onChange={(e) => { setVerdict(e.target.value); setPage(1) }} className="min-w-[10rem]">
        <option value="" className="bg-white">All verdicts</option>
        {DETECTION_VERDICTS.map((v) => (
          <option key={v} value={v} className="bg-white">{v.replace(/_/g, ' ')}</option>
        ))}
      </SelectField>

      <ErrorBanner error={error} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[780px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">When</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Stage 1</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Confidence</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Attack family</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Anomaly</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Verdict</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Severity</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-5 py-10 text-center text-slate-500">
                    No detections yet.
                  </td>
                </tr>
              )}
              {items.map((d) => (
                <tr
                  key={d.id}
                  onClick={() => navigate(`/detections/${d.id}`)}
                  className="cursor-pointer transition-colors hover:bg-slate-100"
                >
                  <td className="px-5 py-3.5 text-slate-600">
                    {d.detected_at ? new Date(d.detected_at).toLocaleString() : '—'}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="flex items-center gap-2 text-slate-800">
                      <ActivityIcon className="h-3.5 w-3.5 text-slate-500" />
                      {d.stage1_label}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-600">
                    {d.stage1_probability != null ? d.stage1_probability.toFixed(4) : '—'}
                  </td>
                  <td className="px-5 py-3.5 text-slate-700">
                    {d.stage2_attack_family ? (
                      <>
                        {d.stage2_attack_family}
                        {d.stage2_confidence != null && (
                          <span className="ml-1.5 font-mono text-xs text-slate-500">({d.stage2_confidence.toFixed(2)})</span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    {d.stage3_is_anomaly ? (
                      <span className="flex items-center gap-1.5 text-orange-700" title={`anomaly score ${d.stage3_anomaly_score?.toFixed(3)}`}>
                        <AlertTriangleIcon className="h-3.5 w-3.5" />
                        <span className="font-mono text-xs">{d.stage3_anomaly_score?.toFixed(2)}</span>
                      </span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs capitalize ring-1 ring-inset ${VERDICT_STYLES[d.final_verdict] || ''}`}
                    >
                      {d.final_verdict.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className={`px-5 py-3.5 capitalize ${SEVERITY_STYLES[d.severity] || 'text-slate-600'}`}>
                    {d.severity}
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500">
                    {d.inference_latency_ms != null ? `${d.inference_latency_ms.toFixed(2)} ms` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {total > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3.5 text-xs text-slate-500">
            <span>
              {total} detection{total === 1 ? '' : 's'} · page {page} of {totalPages}
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
