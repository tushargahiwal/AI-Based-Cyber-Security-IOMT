import { useState } from 'react'
import { Link } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import { listNotifications, retryNotification, getLiveStatus, NOTIFICATION_CHANNELS } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import SelectField from '../components/SelectField'
import { BellIcon, CheckCircleIcon, AlertTriangleIcon, SpinnerIcon } from '../components/icons'

const STATUS_STYLES = {
  sent: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  pending: 'bg-amber-50 text-amber-700 ring-amber-200',
  failed: 'bg-red-50 text-red-700 ring-red-200',
}

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

export default function Notifications() {
  const { user } = useCurrentUser()
  const canRetry = hasPermission(user, 'alerts.ack')

  const [filters, setFilters] = useState({ status: '', channel: '' })
  const { data, loading, error, reload } = useApi(
    () => listNotifications({ size: 50, status: filters.status || undefined, channel: filters.channel || undefined }),
    [filters.status, filters.channel],
  )
  const { data: live } = useApi(getLiveStatus, [])
  const [busyId, setBusyId] = useState(null)
  const [actionError, setActionError] = useState(null)

  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }))

  const retry = async (id) => {
    setBusyId(id)
    setActionError(null)
    try {
      await retryNotification(id)
      reload()
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Retry failed.'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />
      {actionError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {actionError}
        </div>
      )}

      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-40">
            <SelectField label="Status" value={filters.status} onChange={set('status')}>
              <option value="" className="bg-white text-slate-500">All</option>
              {['pending', 'sent', 'failed'].map((s) => (
                <option key={s} value={s} className="bg-white text-slate-900">{s}</option>
              ))}
            </SelectField>
          </div>
          <div className="w-44">
            <SelectField label="Channel" icon={BellIcon} value={filters.channel} onChange={set('channel')}>
              <option value="" className="bg-white text-slate-500">All</option>
              {NOTIFICATION_CHANNELS.map((c) => (
                <option key={c} value={c} className="bg-white text-slate-900">{c}</option>
              ))}
            </SelectField>
          </div>
          <span className="ml-auto text-xs text-slate-500">
            {live ? `${live.listeners} live listener${live.listeners === 1 ? '' : 's'} connected` : ''}
          </span>
        </div>
      </Card>

      <Card title={`Notifications${data ? ` (${data.total})` : ''}`}>
        {loading && !data && <p className="text-sm text-slate-500">Loading…</p>}
        {data?.items.length === 0 && (
          <p className="text-sm text-slate-500">
            Nothing yet. Notifications are raised for high and critical alerts only.
          </p>
        )}

        <div className="space-y-2">
          {data?.items.map((n) => (
            <div
              key={n.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-3"
            >
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset ${STATUS_STYLES[n.status] || ''}`}
              >
                {n.status}
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 ring-1 ring-inset ring-slate-200">
                {n.channel}
              </span>

              <Link to={`/alerts/${n.alert_id}`} className="text-sm text-slate-800 hover:text-sky-800">
                {n.payload?.title || n.alert_uid || `Alert #${n.alert_id}`}
              </Link>

              {n.error_message && (
                <span className="flex items-center gap-1.5 text-xs text-slate-500">
                  <AlertTriangleIcon className="h-3.5 w-3.5" />
                  {n.error_message}
                </span>
              )}

              <span className="ml-auto text-xs text-slate-500">
                {n.sent_at ? new Date(n.sent_at).toLocaleString() : 'not sent'}
              </span>

              {n.status === 'sent' ? (
                <CheckCircleIcon className="h-4 w-4 text-emerald-600" />
              ) : (
                canRetry && (
                  <button
                    onClick={() => retry(n.id)}
                    disabled={busyId === n.id}
                    className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs text-slate-800 hover:bg-slate-200 disabled:opacity-50"
                  >
                    {busyId === n.id && <SpinnerIcon className="h-3 w-3 animate-spin" />}
                    Retry{n.retry_count > 0 ? ` (${n.retry_count})` : ''}
                  </button>
                )
              )}
            </div>
          ))}
        </div>

        <p className="mt-4 text-xs text-slate-500">
          Only the live-socket channel delivers in this deployment. Email, SMS, Telegram and webhook rows are
          recorded so the trail of who should have been told survives, but they stay pending until an outbound
          gateway is configured.
        </p>
      </Card>
    </div>
  )
}
