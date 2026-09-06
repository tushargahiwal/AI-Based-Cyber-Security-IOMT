import { useState } from 'react'
import useApi from '../../hooks/useApi'
import { listDatasets, createDataset, updateDataset } from '../../api/client'
import { extractErrorMessage } from '../../api/errors'
import ErrorBanner from '../../components/ErrorBanner'
import TextField from '../../components/TextField'
import { PlusIcon, SpinnerIcon } from '../../components/icons'

const EMPTY = { name: '', version: '', source_url: '', total_records: '', num_features: '', num_classes: '', benign_ratio: '' }

export default function DatasetsPanel() {
  const { data, loading, error, reload } = useApi(listDatasets, [])
  const [adding, setAdding] = useState(false)
  const [newForm, setNewForm] = useState(EMPTY)
  const [addError, setAddError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(EMPTY)
  const [editError, setEditError] = useState(null)

  const items = data || []
  const toNum = (v) => (v === '' ? undefined : Number(v))
  const toNumOrNull = (v) => (v === '' ? null : Number(v))

  const startEdit = (d) => {
    setEditingId(d.id)
    setEditForm({
      name: d.name,
      version: d.version || '',
      source_url: d.source_url || '',
      total_records: d.total_records ?? '',
      num_features: d.num_features ?? '',
      num_classes: d.num_classes ?? '',
      benign_ratio: d.benign_ratio ?? '',
    })
    setEditError(null)
  }

  const submitNew = async (e) => {
    e.preventDefault()
    setAddError(null)
    setBusy(true)
    try {
      await createDataset({
        name: newForm.name.trim(),
        version: newForm.version.trim() || undefined,
        source_url: newForm.source_url.trim() || undefined,
        total_records: toNum(newForm.total_records),
        num_features: toNum(newForm.num_features),
        num_classes: toNum(newForm.num_classes),
        benign_ratio: toNum(newForm.benign_ratio),
      })
      setNewForm(EMPTY)
      setAdding(false)
      reload()
    } catch (err) {
      setAddError(extractErrorMessage(err, 'Could not create this dataset.'))
    } finally {
      setBusy(false)
    }
  }

  const submitEdit = async (id) => {
    setBusy(true)
    setEditError(null)
    try {
      await updateDataset(id, {
        version: editForm.version.trim() || null,
        source_url: editForm.source_url.trim() || null,
        total_records: toNumOrNull(editForm.total_records),
        num_features: toNumOrNull(editForm.num_features),
        num_classes: toNumOrNull(editForm.num_classes),
        benign_ratio: toNumOrNull(editForm.benign_ratio),
      })
      setEditingId(null)
      reload()
    } catch (err) {
      setEditError(extractErrorMessage(err, 'Could not update this dataset.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">ML dataset registry — CICIoMT2024, WUSTL-EHMS-2020, etc.</p>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200"
        >
          <PlusIcon className="h-4 w-4" />
          Add dataset
        </button>
      </div>

      <ErrorBanner error={error} />

      {adding && (
        <form onSubmit={submitNew} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-3">
          <TextField label="Name" placeholder="CICIoMT2024" value={newForm.name} onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))} />
          <TextField label="Version" value={newForm.version} onChange={(e) => setNewForm((f) => ({ ...f, version: e.target.value }))} />
          <TextField label="Source URL" value={newForm.source_url} onChange={(e) => setNewForm((f) => ({ ...f, source_url: e.target.value }))} />
          <TextField label="Total records" type="number" value={newForm.total_records} onChange={(e) => setNewForm((f) => ({ ...f, total_records: e.target.value }))} />
          <TextField label="Num features" type="number" value={newForm.num_features} onChange={(e) => setNewForm((f) => ({ ...f, num_features: e.target.value }))} />
          <TextField label="Num classes" type="number" value={newForm.num_classes} onChange={(e) => setNewForm((f) => ({ ...f, num_classes: e.target.value }))} />
          <div className="sm:col-span-3 flex items-center gap-3">
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
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Name</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Version</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Records</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Features</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Classes</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">No datasets registered.</td></tr>
              )}
              {items.map((d) =>
                editingId === d.id ? (
                  <tr key={d.id} className="bg-slate-50">
                    <td className="px-4 py-2.5 text-slate-700">{d.name}</td>
                    <td className="px-4 py-2.5"><TextField value={editForm.version} onChange={(e) => setEditForm((f) => ({ ...f, version: e.target.value }))} /></td>
                    <td className="px-4 py-2.5"><TextField type="number" value={editForm.total_records} onChange={(e) => setEditForm((f) => ({ ...f, total_records: e.target.value }))} /></td>
                    <td className="px-4 py-2.5"><TextField type="number" value={editForm.num_features} onChange={(e) => setEditForm((f) => ({ ...f, num_features: e.target.value }))} /></td>
                    <td className="px-4 py-2.5"><TextField type="number" value={editForm.num_classes} onChange={(e) => setEditForm((f) => ({ ...f, num_classes: e.target.value }))} /></td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => submitEdit(d.id)} disabled={busy} className="rounded-lg bg-sky-500 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-600 disabled:opacity-60">Save</button>
                        <button onClick={() => setEditingId(null)} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100">Cancel</button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={d.id} onClick={() => startEdit(d)} className="cursor-pointer transition-colors hover:bg-slate-100">
                    <td className="px-4 py-2.5 text-slate-800">{d.name}</td>
                    <td className="px-4 py-2.5 text-slate-600">{d.version || '—'}</td>
                    <td className="px-4 py-2.5 text-slate-600">{d.total_records?.toLocaleString() ?? '—'}</td>
                    <td className="px-4 py-2.5 text-slate-600">{d.num_features ?? '—'}</td>
                    <td className="px-4 py-2.5 text-slate-600">{d.num_classes ?? '—'}</td>
                    <td className="px-4 py-2.5" />
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
