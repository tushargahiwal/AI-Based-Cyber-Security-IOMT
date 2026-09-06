import { useState } from 'react'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import { listBlocklist, createBlocklistEntry, updateBlocklistEntry, deleteBlocklistEntry, BLOCKLIST_ENTRY_TYPES } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import ErrorBanner from '../components/ErrorBanner'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import { PlusIcon, TrashIcon, BanIcon, SpinnerIcon } from '../components/icons'

const EMPTY = { entry_type: 'ip', value: '', reason: '', expires_at: '' }

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

export default function Blocklist() {
  const { user } = useCurrentUser()
  const canWrite = hasPermission(user, 'devices.quarantine')

  const [entryTypeFilter, setEntryTypeFilter] = useState('')
  const [activeOnly, setActiveOnly] = useState(true)
  const { data, loading, error, reload } = useApi(
    () => listBlocklist({ entry_type: entryTypeFilter || undefined, is_active: activeOnly ? true : undefined }),
    [entryTypeFilter, activeOnly]
  )

  const [adding, setAdding] = useState(false)
  const [newForm, setNewForm] = useState(EMPTY)
  const [addError, setAddError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [togglingId, setTogglingId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [rowError, setRowError] = useState(null)

  const items = data || []

  const submitNew = async (e) => {
    e.preventDefault()
    setAddError(null)
    setBusy(true)
    try {
      await createBlocklistEntry({
        entry_type: newForm.entry_type,
        value: newForm.value.trim(),
        reason: newForm.reason.trim() || undefined,
        expires_at: newForm.expires_at || undefined,
      })
      setNewForm(EMPTY)
      setAdding(false)
      reload()
    } catch (err) {
      setAddError(extractErrorMessage(err, 'Could not create this blocklist entry.'))
    } finally {
      setBusy(false)
    }
  }

  const toggleActive = async (entry) => {
    setTogglingId(entry.id)
    setRowError(null)
    try {
      await updateBlocklistEntry(entry.id, { is_active: !entry.is_active })
      reload()
    } catch (err) {
      setRowError(extractErrorMessage(err, 'Could not update this entry.'))
    } finally {
      setTogglingId(null)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('Remove this blocklist entry entirely?')) return
    setDeletingId(id)
    setRowError(null)
    try {
      await deleteBlocklistEntry(id)
      reload()
    } catch (err) {
      setRowError(extractErrorMessage(err, 'Could not delete this entry.'))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <SelectField value={entryTypeFilter} onChange={(e) => setEntryTypeFilter(e.target.value)} className="min-w-[9rem]">
            <option value="" className="bg-white">All types</option>
            {BLOCKLIST_ENTRY_TYPES.map((t) => <option key={t} value={t} className="bg-white">{t}</option>)}
          </SelectField>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} className="h-4 w-4 rounded border-slate-300 bg-white accent-sky-500" />
            Active only
          </label>
        </div>

        {canWrite && (
          <button
            type="button"
            onClick={() => setAdding((v) => !v)}
            className="flex items-center gap-1.5 rounded-lg bg-sky-500 px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-600"
          >
            <PlusIcon className="h-4 w-4" />
            Add entry
          </button>
        )}
      </div>

      <ErrorBanner error={error} />
      {rowError && <p className="text-xs text-red-600">{rowError}</p>}

      {adding && canWrite && (
        <form onSubmit={submitNew} className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-4">
          <SelectField label="Type" value={newForm.entry_type} onChange={(e) => setNewForm((f) => ({ ...f, entry_type: e.target.value }))}>
            {BLOCKLIST_ENTRY_TYPES.map((t) => <option key={t} value={t} className="bg-white">{t}</option>)}
          </SelectField>
          <TextField label="Value" placeholder="192.168.20.55" value={newForm.value} onChange={(e) => setNewForm((f) => ({ ...f, value: e.target.value }))} />
          <TextField label="Reason" placeholder="MQTT flood source" value={newForm.reason} onChange={(e) => setNewForm((f) => ({ ...f, reason: e.target.value }))} />
          <TextField label="Expires at" type="datetime-local" hint="Empty = permanent" value={newForm.expires_at} onChange={(e) => setNewForm((f) => ({ ...f, expires_at: e.target.value }))} />
          <div className="sm:col-span-4 flex items-center gap-3">
            <button type="submit" disabled={busy} className="flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-600 disabled:opacity-60">
              {busy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
              Add
            </button>
            {addError && <span className="text-xs text-red-600">{addError}</span>}
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Value</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Type</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Reason</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Expires</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
                {canWrite && <th className="px-5 py-3" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={canWrite ? 6 : 5} className="px-5 py-10 text-center text-slate-500">
                    No blocklist entries.
                  </td>
                </tr>
              )}
              {items.map((entry) => (
                <tr key={entry.id} className="transition-colors hover:bg-slate-100">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-700">
                        <BanIcon className="h-4 w-4" />
                      </div>
                      <span className="font-mono text-sm text-slate-800">{entry.value}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">{entry.entry_type}</td>
                  <td className="px-5 py-3.5 text-slate-600">{entry.reason || '—'}</td>
                  <td className="px-5 py-3.5 text-slate-600">
                    {entry.expires_at ? new Date(entry.expires_at).toLocaleString() : 'Permanent'}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs ring-1 ring-inset ${
                        entry.is_active
                          ? 'bg-red-50 text-red-700 ring-red-200'
                          : 'bg-slate-100 text-slate-600 ring-slate-200'
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${entry.is_active ? 'bg-red-400' : 'bg-slate-400'}`} />
                      {entry.is_active ? 'Blocked' : 'Inactive'}
                    </span>
                  </td>
                  {canWrite && (
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => toggleActive(entry)}
                          disabled={togglingId === entry.id}
                          className="rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                        >
                          {entry.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                        <button
                          onClick={() => remove(entry.id)}
                          disabled={deletingId === entry.id}
                          title="Delete"
                          className="rounded-lg p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                        >
                          {deletingId === entry.id ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <TrashIcon className="h-4 w-4" />}
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
