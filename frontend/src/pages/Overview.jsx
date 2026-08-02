import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import useApi from '../hooks/useApi'
import useWebSocket from '../hooks/useWebSocket'
import {
  getStatsOverview,
  getAttackDistribution,
  getTrafficTimeline,
  listAlerts,
} from '../api/client'
import StatCard from '../components/StatCard'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import SeverityBadge from '../components/SeverityBadge'
import VerdictBadge from '../components/VerdictBadge'

const DONUT_COLORS = ['#38bdf8', '#f97316', '#ef4444', '#a855f7', '#eab308', '#22c55e']

export default function Overview() {
  const kpis = useApi(getStatsOverview, [])
  const distribution = useApi(getAttackDistribution, [])
  const timeline = useApi(getTrafficTimeline, [])
  const recentAlerts = useApi(() => listAlerts({ page: 1, size: 10 }), [])
  const { messages: liveAlerts } = useWebSocket('/ws/alerts', { maxItems: 10 })

  const k = kpis.data || {}
  const alerts = liveAlerts.length ? liveAlerts : recentAlerts.data?.items || recentAlerts.data || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Overview</h1>
        <p className="text-sm text-slate-500">Live posture across every IoMT device on the network.</p>
      </div>

      <ErrorBanner error={kpis.error} label="stats overview" />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Flows today" value={fmt(k.flows_today)} />
        <StatCard label="Attacks today" value={fmt(k.attacks_today)} accent="text-red-300" />
        <StatCard label="Active alerts" value={fmt(k.active_alerts)} accent="text-orange-300" />
        <StatCard label="Devices online" value={fmt(k.devices_online)} accent="text-emerald-300" />
        <StatCard label="Mean time to detect" value={k.mean_time_to_detect ? `${k.mean_time_to_detect}s` : '—'} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Live traffic" className="lg:col-span-2">
          <ErrorBanner error={timeline.error} label="traffic timeline" />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline.data?.points || timeline.data || []}>
                <CartesianGrid stroke="#1f2430" strokeDasharray="4 4" />
                <XAxis dataKey="t" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#0d1017', border: '1px solid #1f2430', fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Line type="monotone" dataKey="benign" stroke="#22c55e" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="malicious" stroke="#ef4444" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card title="Attack distribution">
          <ErrorBanner error={distribution.error} label="attack distribution" />
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={distribution.data?.items || distribution.data || []}
                  dataKey="count"
                  nameKey="family"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={2}
                >
                  {(distribution.data?.items || distribution.data || []).map((_, i) => (
                    <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} />
                  ))}
                </Pie>
                <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
                <Tooltip contentStyle={{ background: '#0d1017', border: '1px solid #1f2430', fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card title="Latest alerts">
        <ErrorBanner error={recentAlerts.error} label="alerts" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-4">Title</th>
                <th className="pb-2 pr-4">Device</th>
                <th className="pb-2 pr-4">Verdict</th>
                <th className="pb-2 pr-4">Severity</th>
                <th className="pb-2">Detected</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {alerts.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500">
                    No alerts yet.
                  </td>
                </tr>
              )}
              {alerts.map((a) => (
                <tr key={a.id || a.alert_uid} className="text-slate-300">
                  <td className="py-2 pr-4">{a.title}</td>
                  <td className="py-2 pr-4 text-slate-400">{a.device_id ?? a.device?.device_uid ?? '—'}</td>
                  <td className="py-2 pr-4">
                    <VerdictBadge verdict={a.final_verdict || a.verdict} />
                  </td>
                  <td className="py-2 pr-4">
                    <SeverityBadge severity={a.severity} />
                  </td>
                  <td className="py-2 text-slate-500">{formatTime(a.first_seen_at || a.detected_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function fmt(n) {
  if (n === undefined || n === null) return '—'
  return new Intl.NumberFormat().format(n)
}

function formatTime(t) {
  if (!t) return '—'
  try {
    return new Date(t).toLocaleTimeString()
  } catch {
    return t
  }
}
