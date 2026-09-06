import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import { listModels, MODEL_STAGES } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import SelectField from '../components/SelectField'
import { PlusIcon, CpuIcon, CheckCircleIcon } from '../components/icons'

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

export default function Models() {
  const navigate = useNavigate()
  const { user } = useCurrentUser()
  const [stage, setStage] = useState('')

  const { data, loading, error } = useApi(() => listModels({ stage: stage || undefined }), [stage])
  const items = data || []
  const canRegister = hasPermission(user, 'models.retrain')

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SelectField value={stage} onChange={(e) => setStage(e.target.value)} className="min-w-[9rem]">
          <option value="" className="bg-white">All stages</option>
          {MODEL_STAGES.map((s) => <option key={s} value={s} className="bg-white">Stage {s}</option>)}
        </SelectField>

        {canRegister && (
          <Link
            to="/models/new"
            className="flex items-center gap-1.5 rounded-lg bg-sky-500 px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-600"
          >
            <PlusIcon className="h-4 w-4" />
            Register Model
          </Link>
        )}
      </div>

      <ErrorBanner error={error} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Model</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Stage</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Algorithm</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Version</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Task</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-500">
                    No models registered.
                  </td>
                </tr>
              )}
              {items.map((m) => (
                <tr
                  key={m.id}
                  onClick={() => navigate(`/models/${m.id}`)}
                  className="cursor-pointer transition-colors hover:bg-slate-100"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-700">
                        <CpuIcon className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-800">{m.display_name || m.model_code}</p>
                        <p className="font-mono text-[11px] text-slate-500">{m.model_code}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">{m.stage ? `Stage ${m.stage}` : '—'}</td>
                  <td className="px-5 py-3.5 text-slate-600">{m.algorithm || '—'}</td>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-600">{m.version}</td>
                  <td className="px-5 py-3.5 text-slate-600">{m.task_type || '—'}</td>
                  <td className="px-5 py-3.5">
                    {m.is_active ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700 ring-1 ring-inset ring-emerald-200">
                        <CheckCircleIcon className="h-3.5 w-3.5" />
                        Active
                      </span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 ring-1 ring-inset ring-slate-200">
                        Inactive
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
