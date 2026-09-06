import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import { listPatients, listWards } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import SelectField from '../components/SelectField'
import { PlusIcon, MapPinIcon, HeartPulseIcon } from '../components/icons'

const PAGE_SIZE = 20

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

export default function Patients() {
  const navigate = useNavigate()
  const { user } = useCurrentUser()
  const [page, setPage] = useState(1)
  const [ward, setWard] = useState('')
  const [includeDischarged, setIncludeDischarged] = useState(false)

  const { data, loading, error } = useApi(
    () => listPatients({ page, size: PAGE_SIZE, ward: ward || undefined, include_discharged: includeDischarged }),
    [page, ward, includeDischarged]
  )
  const { data: wards } = useApi(listWards, [])

  const items = data?.items || []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const canRegister = hasPermission(user, 'patients.write')

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <SelectField value={ward} onChange={(e) => { setWard(e.target.value); setPage(1) }} className="min-w-[9rem]">
            <option value="" className="bg-white">All wards</option>
            {(wards || []).map((w) => (
              <option key={w.id} value={w.name} className="bg-white">{w.name}</option>
            ))}
          </SelectField>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={includeDischarged}
              onChange={(e) => { setIncludeDischarged(e.target.checked); setPage(1) }}
              className="h-4 w-4 rounded border-slate-300 bg-white accent-sky-500"
            />
            Include discharged
          </label>
        </div>

        {canRegister && (
          <Link
            to="/patients/new"
            className="flex items-center gap-1.5 rounded-lg bg-sky-500 px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-600"
          >
            <PlusIcon className="h-4 w-4" />
            Admit Patient
          </Link>
        )}
      </div>

      <ErrorBanner error={error} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Patient</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Age band</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Sex</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Ward</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-slate-500">
                    No patients found.
                  </td>
                </tr>
              )}
              {items.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => navigate(`/patients/${p.id}`)}
                  className="cursor-pointer transition-colors hover:bg-slate-100"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-700">
                        <HeartPulseIcon className="h-4 w-4" />
                      </div>
                      <p className="font-medium text-slate-800">{p.patient_code}</p>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">{p.age_band || '—'}</td>
                  <td className="px-5 py-3.5 text-slate-600">{p.sex || '—'}</td>
                  <td className="px-5 py-3.5 text-slate-600">
                    {p.ward ? (
                      <span className="flex items-center gap-1.5">
                        <MapPinIcon className="h-3.5 w-3.5 text-slate-500" />
                        {p.ward.name}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs ring-1 ring-inset ${
                        p.discharged_at
                          ? 'bg-slate-100 text-slate-600 ring-slate-200'
                          : 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${p.discharged_at ? 'bg-slate-400' : 'bg-emerald-400'}`} />
                      {p.discharged_at ? 'Discharged' : 'Admitted'}
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
              {total} patient{total === 1 ? '' : 's'} · page {page} of {totalPages}
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
