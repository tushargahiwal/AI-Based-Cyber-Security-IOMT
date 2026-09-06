import { useState } from 'react'
import useApi from '../../hooks/useApi'
import { listThresholds, createThreshold, updateThreshold, deleteThreshold, THRESHOLD_SCOPES } from '../../api/client'
import { extractErrorMessage } from '../../api/errors'
import ErrorBanner from '../../components/ErrorBanner'
import TextField from '../../components/TextField'
import SelectField from '../../components/SelectField'
import { PlusIcon, TrashIcon, SpinnerIcon } from '../../components/icons'

const EMPTY = { scope: 'global', scope_id: '', metric: '', min_value: '', max_value: '', max_delta_per_sec: '' }

export default function ThresholdsPanel() {
  const { data, loading, error, reload } = useApi(listThresholds, [])
  const [adding, setAdding] = useState(false)
  const [newForm, setNewForm] = useState(EMPTY)
  const [addError, setAddError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(EMPTY)
  const [editError, setEditError] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  const items = data || []

  const startEdit = (t) => {
    setEditingId(t.id)
    setEditForm({
      scope: t.scope,
      scope_id: t.scope_id ?? '',
      metric: t.metric,
      min_value: t.min_value ?? '',
      max_value: t.max_value ?? '',
      max_delta_per_sec: t.max_delta_per_sec ?? '',
    })
    setEditError(null)
  }

  const toNum = (v) => (v === '' ? undefined : Number(v))
  const toNumOrNull = (v) => (v === '' ? null : Number(v))

  const submitNew = async (e) => {
    e.preventDefault()
    setAddError(null)
    setBusy(true)
    try {
      await createThreshold({
        scope: newForm.scope,
        scope_id: newForm.scope === 'global' ? undefined : toNum(newForm.scope_id),
        metric: newForm.metric.trim(),
        min_value: toNum(newForm.min_value),
        max_value: toNum(newForm.max_value),
        max_delta_per_sec: toNum(newForm.max_delta_per_sec),
      })
      setNewForm(EMPTY)
      setAdding(false)
      reload()
    } catch (err) {
      setAddError(extractErrorMessage(err, 'Could not create this threshold.'))
    } finally {
      setBusy(false)
    }
  }

  const submitEdit = async (id) => {
    setBusy(true)
    setEditError(null)
    try {
      await updateThreshold(id, {
        min_value: toNumOrNull(editForm.min_value),
        max_value: toNumOrNull(editForm.max_value),
        max_delta_per_sec: toNumOrNull(editForm.max_delta_per_sec),
      })
      setEditingId(null)
      reload()
    } catch (err) {
      setEditError(extractErrorMessage(err, 'Could not update this threshold.'))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('Delete this threshold?')) return
    setDeletingId(id)
    try {
      await deleteThreshold(id)
      reload()
    } catch (err) {
      setEditError(extractErrorMessage(err, 'Could not delete this threshold.'))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">Vital / metric limits used by Stage 4's rule layer.</p>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200"
        >
          <PlusIcon className="h-4 w-4" />
          Add threshold
        </button>
      </div>

      <ErrorBanner error={error} />

      {adding && (
        <form onSubmit={submitNew} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-6">
          <SelectField label="Scope" value={newForm.scope} onChange={(e) => setNewForm((f) => ({ ...f, scope: e.target.value }))}>
            {THRESHOLD_SCOPES.map((s) => <option key={s} value={s} className="bg-white">{s}</option>)}
          </SelectField>
          <TextField
            label="Scope ID"
            type="number"
            placeholder={newForm.scope === 'global' ? 'n/a' : 'required'}
            disabled={newForm.scope === 'global'}
            value={newForm.scope_id}
            onChange={(e) => setNewForm((f) => ({ ...f, scope_id: e.target.value }))}
          />
          <TextField label="Metric" placeholder="heart_rate" value={newForm.metric} onChange={(e) => setNewForm((f) => ({ ...f, metric: e.target.value }))} />
          <TextField label="Min" type="number" value={newForm.min_value} onChange={(e) => setNewForm((f) => ({ ...f, min_value: e.target.value }))} />
          <TextField label="Max" type="number" value={newForm.max_value} onChange={(e) => setNewForm((f) => ({ ...f, max_value: e.target.value }))} />
          <TextField label="Max delta/sec" type="number" value={newForm.max_delta_per_sec} onChange={(e) => setNewForm((f) => ({ ...f, max_delta_per_sec: e.target.value }))} />
          <div className="sm:col-span-6 flex items-center gap-3">
            <button type="submit" disabled={busy} className="flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-600 disabled:opacity-60">
              {busy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
              Create
            </button>
            {addError && <span className="text-xs text-red-600">{addError}</span>}
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Scope</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Metric</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Min</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Max</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Max Δ/sec</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">No thresholds defined.</td></tr>
              )}
              {items.map((t) =>
                editingId === t.id ? (
                  <tr key={t.id} className="bg-slate-50">
                    <td className="px-4 py-2.5 text-slate-600">{t.scope}{t.scope_id ? ` #${t.scope_id}` : ''}</td>
                    <td className="px-4 py-2.5 text-slate-700">{t.metric}</td>
                    <td className="px-4 py-2.5"><TextField type="number" value={editForm.min_value} onChange={(e) => setEditForm((f) => ({ ...f, min_value: e.target.value }))} /></td>
                    <td className="px-4 py-2.5"><TextField type="number" value={editForm.max_value} onChange={(e) => setEditForm((f) => ({ ...f, max_value: e.target.value }))} /></td>
                    <td className="px-4 py-2.5"><TextField type="number" value={editForm.max_delta_per_sec} onChange={(e) => setEditForm((f) => ({ ...f, max_delta_per_sec: e.target.value }))} /></td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => submitEdit(t.id)} disabled={busy} className="rounded-lg bg-sky-500 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-600 disabled:opacity-60">Save</button>
                        <button onClick={() => setEditingId(null)} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100">Cancel</button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={t.id} className="transition-colors hover:bg-slate-100">
                    <td onClick={() => startEdit(t)} className="cursor-pointer px-4 py-2.5 text-slate-600">{t.scope}{t.scope_id ? ` #${t.scope_id}` : ''}</td>
                    <td onClick={() => startEdit(t)} className="cursor-pointer px-4 py-2.5 text-slate-800">{t.metric}</td>
                    <td onClick={() => startEdit(t)} className="cursor-pointer px-4 py-2.5 text-slate-600">{t.min_value ?? '—'}</td>
                    <td onClick={() => startEdit(t)} className="cursor-pointer px-4 py-2.5 text-slate-600">{t.max_value ?? '—'}</td>
                    <td onClick={() => startEdit(t)} className="cursor-pointer px-4 py-2.5 text-slate-600">{t.max_delta_per_sec ?? '—'}</td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => remove(t.id)}
                        disabled={deletingId === t.id}
                        title="Delete"
                        className="rounded-lg p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                      >
                        {deletingId === t.id ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <TrashIcon className="h-4 w-4" />}
                      </button>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      </div>
      {editError && <p className="text-xs text-red-600">{editError}</p>}
    </div>
  )
}
