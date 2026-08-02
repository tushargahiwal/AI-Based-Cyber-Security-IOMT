import { useParams, Link } from 'react-router-dom'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import useApi from '../hooks/useApi'
import { getDevice, getDeviceVitals, getDeviceTimeline } from '../api/client'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import SeverityBadge from '../components/SeverityBadge'
import VerdictBadge from '../components/VerdictBadge'

export default function DeviceDetail() {
  const { id } = useParams()
  const device = useApi(() => getDevice(id), [id])
  const vitals = useApi(() => getDeviceVitals(id), [id])
  const timeline = useApi(() => getDeviceTimeline(id), [id])

  const d = device.data || {}
  const vitalsRows = vitals.data?.items || vitals.data || []
  const timelineRows = timeline.data?.items || timeline.data || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/devices" className="text-xs text-slate-500 hover:text-slate-300">
            ← Devices
          </Link>
          <h1 className="text-lg font-semibold text-slate-100">{d.device_uid || `Device ${id}`}</h1>
          <p className="text-sm text-slate-500">
            {d.device_type?.type_name || 'Unknown type'} · {d.ward?.name || 'Unassigned ward'}
          </p>
        </div>
        <div className="text-right text-xs text-slate-500">
          <p>Trust score</p>
          <p className="text-xl font-semibold text-slate-100">{d.trust_score ?? '—'}</p>
        </div>
      </div>

      <ErrorBanner error={device.error} label="device detail" />

      <Card title="Vitals — predicted vs actual">
        <ErrorBanner error={vitals.error} label="vitals stream" />
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={vitalsRows}>
              <CartesianGrid stroke="#1f2430" strokeDasharray="4 4" />
              <XAxis dataKey="recorded_at" stroke="#64748b" fontSize={11} tickFormatter={formatTime} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip
                contentStyle={{ background: '#0d1017', border: '1px solid #1f2430', fontSize: 12 }}
                labelFormatter={formatTime}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              <Line type="monotone" dataKey="heart_rate" name="Heart rate (actual)" stroke="#38bdf8" dot={false} strokeWidth={2} />
              <Line
                type="monotone"
                dataKey="predicted_values.heart_rate"
                name="Heart rate (predicted)"
                stroke="#a855f7"
                strokeDasharray="4 4"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        {vitalsRows.some((v) => v.injection_suspected) && (
          <p className="mt-2 text-xs text-rose-300">
            ⚠ Data-injection suspected in this window — actual readings deviate from the LSTM forecast beyond the z-score threshold.
          </p>
        )}
      </Card>

      <Card title="Detection & alert timeline">
        <ErrorBanner error={timeline.error} label="device timeline" />
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-4">Time</th>
                <th className="pb-2 pr-4">Verdict</th>
                <th className="pb-2 pr-4">Severity</th>
                <th className="pb-2">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {timelineRows.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-slate-500">
                    No detections recorded for this device yet.
                  </td>
                </tr>
              )}
              {timelineRows.map((row, i) => (
                <tr key={row.id || i} className="text-slate-300">
                  <td className="py-2 pr-4 text-slate-500">{formatDateTime(row.detected_at)}</td>
                  <td className="py-2 pr-4">
                    <VerdictBadge verdict={row.final_verdict} />
                  </td>
                  <td className="py-2 pr-4">
                    <SeverityBadge severity={row.severity} />
                  </td>
                  <td className="py-2 text-slate-400">
                    {row.final_confidence ? `${Math.round(row.final_confidence * 100)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function formatTime(t) {
  if (!t) return ''
  try {
    return new Date(t).toLocaleTimeString()
  } catch {
    return t
  }
}

function formatDateTime(t) {
  if (!t) return '—'
  try {
    return new Date(t).toLocaleString()
  } catch {
    return t
  }
}
