import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import useWebSocket from '../hooks/useWebSocket'
import Card from '../components/Card'
import { ActivityIcon, AlertTriangleIcon, SpinnerIcon, TrashIcon } from '../components/icons'

const VERDICT_STYLES = {
  benign: 'text-emerald-700',
  known_attack: 'text-red-700',
  uncertain: 'text-amber-700',
  zero_day_suspect: 'text-orange-700',
  data_integrity: 'text-purple-700',
}

const STATUS_LABEL = {
  idle: 'paused',
  connecting: 'connecting…',
  connected: 'live',
  reconnecting: 'reconnecting…',
  error: 'connection error',
  unauthenticated: 'not signed in',
}

const STATUS_STYLE = {
  connected: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  connecting: 'bg-amber-50 text-amber-700 ring-amber-200',
  reconnecting: 'bg-amber-50 text-amber-700 ring-amber-200',
  error: 'bg-red-50 text-red-700 ring-red-200',
  idle: 'bg-slate-100 text-slate-600 ring-slate-200',
  unauthenticated: 'bg-red-50 text-red-700 ring-red-200',
}

function Stat({ label, value, tone = 'text-slate-900' }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  )
}

export default function LiveMonitor() {
  const [running, setRunning] = useState(true)
  const { events, status, clear } = useWebSocket({ enabled: running, limit: 150 })

  const detections = useMemo(() => events.filter((e) => e.type === 'detection'), [events])

  // Counted over the visible tail rather than all time — this panel answers
  // "what is happening right now", and the dashboard covers the totals.
  const counts = useMemo(() => {
    const c = { flagged: 0, alerts: 0, stage4: 0 }
    for (const e of detections) {
      if (e.data.final_verdict !== 'benign') c.flagged += 1
      if (e.data.alert_uid) c.alerts += 1
      if (e.data.stage4_injection_suspected) c.stage4 += 1
    }
    return c
  }, [detections])

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs ring-1 ring-inset ${STATUS_STYLE[status] || STATUS_STYLE.idle}`}
          >
            {(status === 'connecting' || status === 'reconnecting') && (
              <SpinnerIcon className="h-3 w-3 animate-spin" />
            )}
            {status === 'connected' && <span className="h-2 w-2 rounded-full bg-emerald-400" />}
            {STATUS_LABEL[status] || status}
          </span>

          <button
            onClick={() => setRunning((r) => !r)}
            className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200"
          >
            {running ? 'Pause' : 'Resume'}
          </button>
          <button
            onClick={clear}
            disabled={events.length === 0}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200 disabled:opacity-50"
          >
            <TrashIcon className="h-3.5 w-3.5" />
            Clear
          </button>

          <span className="ml-auto text-xs text-slate-500">
            Showing the last {events.length} events. Nothing is replayed on connect — start a stream with{' '}
            <span className="font-mono text-slate-600">workers.replay</span> or the Attack Simulator.
          </span>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Events in view" value={detections.length} />
        <Stat label="Flagged" value={counts.flagged} tone={counts.flagged ? 'text-amber-700' : 'text-slate-900'} />
        <Stat label="Alerts raised" value={counts.alerts} tone={counts.alerts ? 'text-red-700' : 'text-slate-900'} />
        <Stat label="Vitals implausible" value={counts.stage4} tone={counts.stage4 ? 'text-purple-700' : 'text-slate-900'} />
      </div>

      <Card title="Live feed">
        {events.length === 0 ? (
          <p className="text-sm text-slate-500">
            {status === 'connected'
              ? 'Connected and waiting for traffic.'
              : 'Not receiving events yet.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] text-sm">
              <thead>
                <tr className="text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th className="pb-2">Time</th>
                  <th className="pb-2">Flow</th>
                  <th className="pb-2">Stage 1</th>
                  <th className="pb-2">Signals</th>
                  <th className="pb-2">Verdict</th>
                  <th className="pb-2">Alert</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e, i) => {
                  if (e.type !== 'detection') {
                    return (
                      <tr key={`${e.receivedAt}-${i}`} className="border-t border-slate-100">
                        <td className="py-2 text-xs text-slate-500">
                          {new Date(e.receivedAt).toLocaleTimeString()}
                        </td>
                        <td className="py-2 text-red-700" colSpan={5}>
                          <span className="flex items-center gap-2">
                            <AlertTriangleIcon className="h-3.5 w-3.5" />
                            {e.data.title}
                          </span>
                        </td>
                      </tr>
                    )
                  }
                  const d = e.data
                  return (
                    <tr key={`${e.receivedAt}-${i}`} className="border-t border-slate-100">
                      <td className="py-2 text-xs text-slate-500">
                        {new Date(e.receivedAt).toLocaleTimeString()}
                      </td>
                      <td className="py-2 font-mono text-xs text-slate-600">
                        {d.src_ip} → {d.dst_ip}
                      </td>
                      <td className="py-2 tabular-nums text-slate-700">
                        {d.stage1_probability?.toFixed(3)}
                      </td>
                      <td className="py-2">
                        <span className="flex gap-1.5 text-[10px]">
                          {d.stage3_is_anomaly && (
                            <span className="rounded bg-orange-50 px-1.5 py-0.5 text-orange-700">S3</span>
                          )}
                          {d.stage4_injection_suspected && (
                            <span className="rounded bg-purple-50 px-1.5 py-0.5 text-purple-700">S4</span>
                          )}
                        </span>
                      </td>
                      <td className={`py-2 capitalize ${VERDICT_STYLES[d.final_verdict] || 'text-slate-700'}`}>
                        {d.final_verdict.replace(/_/g, ' ')}
                      </td>
                      <td className="py-2">
                        {d.alert_uid ? (
                          <span className="flex items-center gap-1.5 text-xs text-red-700">
                            <ActivityIcon className="h-3 w-3" />
                            {d.alert_uid}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-600">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-4 text-xs text-slate-500">
          Every detection appears here, benign included — a steady wall of benign traffic is what makes the
          occasional flagged flow stand out. Open one from <Link to="/detections" className="text-sky-600 hover:text-sky-800">Detections</Link>.
        </p>
      </Card>
    </div>
  )
}
