import { Link } from 'react-router-dom'
import useApi from '../hooks/useApi'
import { listDevices, updateDevice } from '../api/client'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'

const STATUS_DOT = {
  online: 'bg-emerald-400',
  offline: 'bg-slate-500',
  quarantined: 'bg-orange-400',
  maintenance: 'bg-yellow-400',
}

export default function Devices() {
  const devices = useApi(listDevices, [])
  const rows = devices.data?.items || devices.data || []

  const quarantine = async (id, currentStatus) => {
    const next = currentStatus === 'quarantined' ? 'online' : 'quarantined'
    await updateDevice(id, { status: next })
    devices.reload()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Devices</h1>
        <p className="text-sm text-slate-500">Registered IoMT endpoints and their trust posture.</p>
      </div>

      <ErrorBanner error={devices.error} label="device inventory" />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {rows.length === 0 && !devices.loading && (
          <p className="col-span-full text-sm text-slate-500">No devices registered yet.</p>
        )}
        {rows.map((d) => (
          <Card key={d.id} className="flex flex-col gap-3">
            <div className="flex items-start justify-between">
              <div>
                <Link to={`/devices/${d.id}`} className="text-sm font-semibold text-slate-100 hover:text-sky-300">
                  {d.device_uid}
                </Link>
                <p className="text-xs text-slate-500">{d.device_type?.type_name || `type ${d.device_type_id}`}</p>
              </div>
              <span className="flex items-center gap-1.5 text-xs text-slate-400">
                <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[d.status] || STATUS_DOT.offline}`} />
                {d.status}
              </span>
            </div>

            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-slate-500">Ward</dt>
                <dd className="text-slate-300">{d.ward?.name || d.ward_id || '—'}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Trust score</dt>
                <dd className={trustColor(d.trust_score)}>{d.trust_score ?? '—'}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-slate-500">Last seen</dt>
                <dd className="text-slate-300">{formatTime(d.last_seen_at)}</dd>
              </div>
            </dl>

            <button
              onClick={() => quarantine(d.id, d.status)}
              className="mt-auto rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10"
            >
              {d.status === 'quarantined' ? 'Release from quarantine' : 'Quarantine device'}
            </button>
          </Card>
        ))}
      </div>
    </div>
  )
}

function trustColor(score) {
  if (score == null) return 'text-slate-300'
  if (score >= 80) return 'text-emerald-300'
  if (score >= 50) return 'text-yellow-300'
  return 'text-red-300'
}

function formatTime(t) {
  if (!t) return '—'
  try {
    return new Date(t).toLocaleString()
  } catch {
    return t
  }
}
