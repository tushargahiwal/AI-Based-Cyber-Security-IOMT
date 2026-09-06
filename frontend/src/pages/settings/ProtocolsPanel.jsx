import { useState } from 'react'
import useApi from '../../hooks/useApi'
import { listProtocols, createProtocol, updateProtocol } from '../../api/client'
import { extractErrorMessage } from '../../api/errors'
import ErrorBanner from '../../components/ErrorBanner'
import TextField from '../../components/TextField'
import { PlusIcon, SpinnerIcon } from '../../components/icons'

const EMPTY = { name: '', default_port: '', is_medical: false }

export default function ProtocolsPanel() {
  const { data, loading, error, reload } = useApi(listProtocols, [])
  const [adding, setAdding] = useState(false)
  const [newForm, setNewForm] = useState(EMPTY)
  const [addError, setAddError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(EMPTY)
  const [editError, setEditError] = useState(null)

  const items = data || []

  const startEdit = (p) => {
    setEditingId(p.id)
    setEditForm({ name: p.name, default_port: p.default_port ?? '', is_medical: p.is_medical })
    setEditError(null)
  }

  const submitNew = async (e) => {
    e.preventDefault()
    setAddError(null)
    setBusy(true)
    try {
      await createProtocol({
        name: newForm.name.trim(),
        default_port: newForm.default_port === '' ? undefined : Number(newForm.default_port),
        is_medical: newForm.is_medical,
      })
      setNewForm(EMPTY)
      setAdding(false)
      reload()
    } catch (err) {
      setAddError(extractErrorMessage(err, 'Could not create this protocol.'))
    } finally {
      setBusy(false)
    }
  }

  const submitEdit = async (id) => {
    setBusy(true)
    setEditError(null)
    try {
      await updateProtocol(id, {
        default_port: editForm.default_port === '' ? null : Number(editForm.default_port),
        is_medical: editForm.is_medical,
      })
      setEditingId(null)
      reload()
    } catch (err) {
      setEditError(extractErrorMessage(err, 'Could not update this protocol.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">Protocol lookup used by dashboard filters.</p>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200"
        >
          <PlusIcon className="h-4 w-4" />
          Add protocol
        </button>
      </div>

      <ErrorBanner error={error} />

      {adding && (
        <form onSubmit={submitNew} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-4 sm:items-end">
          <TextField label="Name" placeholder="MQTT" value={newForm.name} onChange={(e) => setNewForm((f) => ({ ...f, name: e.target.value }))} />
          <TextField label="Default port" type="number" placeholder="1883" value={newForm.default_port} onChange={(e) => setNewForm((f) => ({ ...f, default_port: e.target.value }))} />
          <label className="flex items-center gap-2 pb-2.5 text-sm text-slate-700">
            <input type="checkbox" checked={newForm.is_medical} onChange={(e) => setNewForm((f) => ({ ...f, is_medical: e.target.checked }))} className="h-4 w-4 rounded border-slate-300 bg-white accent-sky-500" />
            Medical protocol
          </label>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={busy} className="flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-600 disabled:opacity-60">
              {busy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
              Create
            </button>
            {addError && <span className="text-xs text-red-600">{addError}</span>}
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Name</th>
              <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Default port</th>
              <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Medical</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {!loading && items.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">No protocols defined.</td></tr>
            )}
            {items.map((p) =>
              editingId === p.id ? (
                <tr key={p.id} className="bg-slate-50">
                  <td className="px-4 py-2.5 text-slate-700">{p.name}</td>
                  <td className="px-4 py-2.5">
                    <TextField type="number" value={editForm.default_port} onChange={(e) => setEditForm((f) => ({ ...f, default_port: e.target.value }))} />
                  </td>
                  <td className="px-4 py-2.5">
                    <input type="checkbox" checked={editForm.is_medical} onChange={(e) => setEditForm((f) => ({ ...f, is_medical: e.target.checked }))} className="h-4 w-4 rounded border-slate-300 bg-white accent-sky-500" />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => submitEdit(p.id)} disabled={busy} className="rounded-lg bg-sky-500 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-600 disabled:opacity-60">Save</button>
                      <button onClick={() => setEditingId(null)} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100">Cancel</button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={p.id} onClick={() => startEdit(p)} className="cursor-pointer transition-colors hover:bg-slate-100">
                  <td className="px-4 py-2.5 text-slate-800">{p.name}</td>
                  <td className="px-4 py-2.5 text-slate-600">{p.default_port ?? '—'}</td>
                  <td className="px-4 py-2.5 text-slate-600">{p.is_medical ? 'Yes' : 'No'}</td>
                  <td className="px-4 py-2.5" />
                </tr>
              )
            )}
          </tbody>
        </table>
      </div>
      {editError && <p className="text-xs text-red-600">{editError}</p>}
    </div>
  )
}
