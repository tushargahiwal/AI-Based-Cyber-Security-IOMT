import { Link } from 'react-router-dom'
import useCurrentUser from '../hooks/useCurrentUser'
import useApi from '../hooks/useApi'
import { getStatsOverview } from '../api/client'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import { ActivityIcon, MonitorIcon, CheckCircleIcon, AlertTriangleIcon, CpuIcon, BellIcon } from '../components/icons'

function KpiCard({ icon: Icon, label, value, accent = 'text-slate-800' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <p className={`mt-2 text-2xl font-semibold ${accent}`}>{value}</p>
    </div>
  )
}

export default function Overview() {
  const { user } = useCurrentUser()
  const { data: stats, loading, error } = useApi(getStatsOverview, [])

  const verdictCounts = stats?.detections_by_verdict || {}
  const attackCount = (verdictCounts.known_attack || 0) + (verdictCounts.zero_day_suspect || 0) + (verdictCounts.data_integrity || 0)

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold text-slate-900">
          {user ? `Welcome, ${user.full_name || user.username}` : 'Dashboard'}
        </h1>
        <p className="text-sm text-slate-500">You&apos;re signed in as {user?.role || 'a user'}.</p>
      </div>

      <ErrorBanner error={error} />

      {stats && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            <KpiCard icon={ActivityIcon} label="Total flows" value={stats.total_flows} />
            <KpiCard icon={CheckCircleIcon} label="Total detections" value={stats.total_detections} />
            <KpiCard
              icon={AlertTriangleIcon}
              label="Flagged attacks"
              value={attackCount}
              accent={attackCount > 0 ? 'text-red-700' : 'text-slate-800'}
            />
            <KpiCard
              icon={BellIcon}
              label="Active alerts"
              value={stats.active_alerts}
              accent={stats.critical_alerts > 0 ? 'text-red-700' : stats.active_alerts > 0 ? 'text-amber-700' : 'text-slate-800'}
            />
            <KpiCard icon={MonitorIcon} label="Devices online" value={`${stats.devices_online} / ${stats.devices_total}`} />
          </div>

          {stats.active_alerts > 0 && (
            <Card title="Active alerts need attention">
              <p className="text-sm text-slate-700">
                <span className="font-semibold text-slate-900">{stats.active_alerts}</span> open alert{stats.active_alerts === 1 ? '' : 's'}
                {stats.critical_alerts > 0 && (
                  <> — <span className="font-semibold text-red-700">{stats.critical_alerts} critical</span></>
                )}
              </p>
              <Link to="/alerts" className="mt-3 inline-block text-sm text-sky-600 hover:text-sky-800">
                Go to Alerts Console →
              </Link>
            </Card>
          )}

          <Card title="Detections by verdict">
            {Object.keys(verdictCounts).length === 0 ? (
              <p className="text-sm text-slate-500">
                No detections yet — submit a flow to <code className="text-slate-600">POST /api/v1/detect</code> to see results here.
              </p>
            ) : (
              <div className="flex flex-wrap gap-3">
                {Object.entries(verdictCounts).map(([verdict, count]) => (
                  <span
                    key={verdict}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm capitalize text-slate-700"
                  >
                    {verdict.replace(/_/g, ' ')}: <span className="font-semibold text-slate-900">{count}</span>
                  </span>
                ))}
              </div>
            )}
            <Link to="/detections" className="mt-4 inline-block text-sm text-sky-600 hover:text-sky-800">
              View all detections →
            </Link>
          </Card>

          <Card title="Active Stage 1 model">
            <div className="flex items-center gap-2 text-sm">
              <CpuIcon className="h-4 w-4 text-slate-500" />
              {stats.active_stage1_model ? (
                <span className="font-mono text-slate-800">{stats.active_stage1_model}</span>
              ) : (
                <span className="text-slate-500">No active Stage 1 model registered.</span>
              )}
            </div>
          </Card>
        </>
      )}

      {loading && !stats && <p className="text-sm text-slate-500">Loading overview…</p>}
    </div>
  )
}
