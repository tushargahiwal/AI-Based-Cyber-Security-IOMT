import { useState } from 'react'
import { generateReport, downloadReport } from '../api/client'
import Card from '../components/Card'

const REPORT_TYPES = ['daily', 'weekly', 'incident', 'compliance', 'custom']

export default function Reports() {
  const [reportType, setReportType] = useState('daily')
  const [status, setStatus] = useState(null)
  const [busy, setBusy] = useState(false)
  const [generated, setGenerated] = useState([])

  const handleGenerate = async () => {
    setBusy(true)
    setStatus(null)
    try {
      const { data } = await generateReport({ report_type: reportType })
      setGenerated((prev) => [data, ...prev])
      setStatus({ ok: true, message: 'Report generated.' })
    } catch (err) {
      setStatus({ ok: false, message: err?.response?.status ? `Failed (HTTP ${err.response.status}).` : 'Backend not reachable yet.' })
    } finally {
      setBusy(false)
    }
  }

  const handleDownload = async (id) => {
    try {
      const { data } = await downloadReport(id)
      const url = window.URL.createObjectURL(new Blob([data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `report-${id}`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      setStatus({ ok: false, message: 'Could not download report.' })
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Reports</h1>
        <p className="text-sm text-slate-500">Generate and download daily, weekly, incident and compliance reports.</p>
      </div>

      <Card title="Generate a report">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            Report type
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="rounded-lg border border-white/10 bg-[#0d1017] px-2 py-1.5 text-sm text-slate-200 focus:border-sky-500/50 focus:outline-none"
            >
              {REPORT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={handleGenerate}
            disabled={busy}
            className="rounded-lg bg-sky-500/15 px-4 py-1.5 text-sm font-medium text-sky-300 ring-1 ring-inset ring-sky-500/30 hover:bg-sky-500/25 disabled:opacity-50"
          >
            {busy ? 'Generating…' : 'Generate'}
          </button>
        </div>
        {status && (
          <p className={`mt-3 text-xs ${status.ok ? 'text-emerald-300' : 'text-amber-300'}`}>{status.message}</p>
        )}
      </Card>

      <Card title="Recent reports (this session)">
        {generated.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing generated yet.</p>
        ) : (
          <ul className="divide-y divide-white/5 text-sm">
            {generated.map((r) => (
              <li key={r.id} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-slate-200">{r.title || `${r.report_type} report`}</p>
                  <p className="text-xs text-slate-500">{r.period_start} → {r.period_end}</p>
                </div>
                <button
                  onClick={() => handleDownload(r.id)}
                  className="rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 hover:bg-white/10"
                >
                  Download
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
