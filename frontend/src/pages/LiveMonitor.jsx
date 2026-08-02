import { useMemo, useState } from 'react'
import useWebSocket from '../hooks/useWebSocket'
import Card from '../components/Card'
import VerdictBadge from '../components/VerdictBadge'

export default function LiveMonitor() {
  const { messages, status } = useWebSocket('/ws/traffic', { maxItems: 300 })
  const [paused, setPaused] = useState(false)
  const [frozen, setFrozen] = useState([])

  const rows = paused ? frozen : messages

  const perDevicePps = useMemo(() => {
    const map = new Map()
    for (const m of messages.slice(0, 50)) {
      const key = m.device_id ?? m.src_ip ?? 'unknown'
      map.set(key, (map.get(key) || 0) + 1)
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6)
  }, [messages])

  const togglePause = () => {
    if (!paused) setFrozen(messages)
    setPaused((p) => !p)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Live Monitor</h1>
          <p className="text-sm text-slate-500">Streaming flow verdicts as they leave the detection pipeline.</p>
        </div>
        <div className="flex items-center gap-3">
          <ConnStatus status={status} />
          <button
            onClick={togglePause}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10"
          >
            {paused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-6">
        {perDevicePps.length === 0 && (
          <p className="col-span-full text-sm text-slate-500">Waiting for live flow data…</p>
        )}
        {perDevicePps.map(([device, count]) => (
          <div key={device} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
            <p className="truncate text-xs text-slate-500">{device}</p>
            <p className="mt-1 text-xl font-semibold text-sky-300">{count}</p>
            <p className="text-[11px] text-slate-600">flows / sample</p>
          </div>
        ))}
      </div>

      <Card title={`Flow stream (${rows.length})`}>
        <div className="max-h-[32rem] overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[#0d1017]">
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-4">Time</th>
                <th className="pb-2 pr-4">Src</th>
                <th className="pb-2 pr-4">Dst</th>
                <th className="pb-2 pr-4">Protocol</th>
                <th className="pb-2 pr-4">Verdict</th>
                <th className="pb-2">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No flows received yet — connect the capture pipeline to see live traffic.
                  </td>
                </tr>
              )}
              {rows.map((r, i) => {
                const isMalicious = r.final_verdict && r.final_verdict !== 'benign'
                return (
                  <tr key={r.flow_uid || i} className={isMalicious ? 'bg-red-500/5' : ''}>
                    <td className="py-1.5 pr-4 text-slate-500">{formatTime(r.detected_at || r.flow_start)}</td>
                    <td className="py-1.5 pr-4 text-slate-300">
                      {r.src_ip}
                      {r.src_port ? `:${r.src_port}` : ''}
                    </td>
                    <td className="py-1.5 pr-4 text-slate-300">
                      {r.dst_ip}
                      {r.dst_port ? `:${r.dst_port}` : ''}
                    </td>
                    <td className="py-1.5 pr-4 text-slate-400">{r.protocol}</td>
                    <td className="py-1.5 pr-4">
                      <VerdictBadge verdict={r.final_verdict || 'benign'} />
                    </td>
                    <td className="py-1.5 text-slate-400">
                      {r.final_confidence ? `${Math.round(r.final_confidence * 100)}%` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function ConnStatus({ status }) {
  const styles = {
    open: 'bg-emerald-400',
    connecting: 'bg-yellow-400 animate-pulse',
    closed: 'bg-red-400',
  }
  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-400">
      <span className={`h-1.5 w-1.5 rounded-full ${styles[status] || styles.closed}`} />
      {status}
    </span>
  )
}

function formatTime(t) {
  if (!t) return '—'
  try {
    return new Date(t).toLocaleTimeString()
  } catch {
    return t
  }
}
