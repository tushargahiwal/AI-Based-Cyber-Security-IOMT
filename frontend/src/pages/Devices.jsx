import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import { listDevices, listDeviceTypes, listWards, DEVICE_STATUSES } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import SelectField from '../components/SelectField'
import { PlusIcon, MapPinIcon, MonitorIcon } from '../components/icons'

const PAGE_SIZE = 20

const STATUS_STYLES = {
  online: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  offline: 'bg-slate-100 text-slate-600 ring-slate-200',
  quarantined: 'bg-red-50 text-red-700 ring-red-200',
  maintenance: 'bg-amber-50 text-amber-700 ring-amber-200',
}

const STATUS_DOT = {
  online: 'bg-emerald-400',
  offline: 'bg-slate-400',
  quarantined: 'bg-red-400',
  maintenance: 'bg-amber-400',
}

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

export default function Devices() {
  const navigate = useNavigate()
  const { user } = useCurrentUser()
  const [page, setPage] = useState(1)
  const [ward, setWard] = useState('')
  const [deviceType, setDeviceType] = useState('')
  const [status, setStatus] = useState('')

  const { data, loading, error } = useApi(
    () => listDevices({ page, size: PAGE_SIZE, ward: ward || undefined, device_type: deviceType || undefined, status: status || undefined }),
    [page, ward, deviceType, status]
  )
  const { data: deviceTypes } = useApi(listDeviceTypes, [])
  const { data: wards } = useApi(listWards, [])

  const items = data?.items || []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const canRegister = hasPermission(user, 'devices.write')

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-3">
          <SelectField value={deviceType} onChange={(e) => { setDeviceType(e.target.value); setPage(1) }} className="min-w-[10rem]">
            <option value="" className="bg-white">All device types</option>
            {(deviceTypes || []).map((dt) => (
              <option key={dt.id} value={dt.type_name} className="bg-white">{dt.type_name}</option>
            ))}
          </SelectField>
          <SelectField value={ward} onChange={(e) => { setWard(e.target.value); setPage(1) }} className="min-w-[9rem]">
            <option value="" className="bg-white">All wards</option>
            {(wards || []).map((w) => (
              <option key={w.id} value={w.name} className="bg-white">{w.name}</option>
            ))}
          </SelectField>
          <SelectField value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} className="min-w-[8rem]">
            <option value="" className="bg-white">All statuses</option>
            {DEVICE_STATUSES.map((s) => (
              <option key={s} value={s} className="bg-white capitalize">{s}</option>
            ))}
          </SelectField>
        </div>

        {canRegister && (
          <Link
            to="/devices/new"
            className="flex items-center gap-1.5 rounded-lg bg-sky-500 px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-600"
          >
            <PlusIcon className="h-4 w-4" />
            Register Device
          </Link>
        )}
      </div>

      <ErrorBanner error={error} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Device</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Type</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Ward</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">IP address</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Trust score</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-500">
                    No devices found.
                  </td>
                </tr>
              )}
              {items.map((d) => (
                <tr
                  key={d.id}
                  onClick={() => navigate(`/devices/${d.id}`)}
                  className="cursor-pointer transition-colors hover:bg-slate-100"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-700">
                        <MonitorIcon className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="truncate font-medium text-slate-800">{d.device_uid}</p>
                        {d.device_type.is_life_critical && (
                          <p className="text-[11px] text-amber-400">Life-critical</p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">{d.device_type.type_name}</td>
                  <td className="px-5 py-3.5 text-slate-600">
                    {d.ward ? (
                      <span className="flex items-center gap-1.5">
                        <MapPinIcon className="h-3.5 w-3.5 text-slate-500" />
                        {d.ward.name}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-600">{d.ip_address || '—'}</td>
                  <td className="px-5 py-3.5 text-slate-700">{d.trust_score.toFixed(0)}</td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs capitalize ring-1 ring-inset ${STATUS_STYLES[d.status]}`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[d.status]}`} />
                      {d.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {total > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3.5 text-xs text-slate-500">
            <span>
              {total} device{total === 1 ? '' : 's'} · page {page} of {totalPages}
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
