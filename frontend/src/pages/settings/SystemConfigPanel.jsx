import { useState } from 'react'
import useApi from '../../hooks/useApi'
import { listSystemConfig, createSystemConfig, updateSystemConfig, deleteSystemConfig, CONFIG_VALUE_TYPES } from '../../api/client'
import { extractErrorMessage } from '../../api/errors'
import ErrorBanner from '../../components/ErrorBanner'
import TextField from '../../components/TextField'
import SelectField from '../../components/SelectField'
import { PlusIcon, TrashIcon, SpinnerIcon } from '../../components/icons'

const EMPTY = { config_key: '', config_value: '', value_type: 'string', description: '' }

export default function SystemConfigPanel() {
  const { data, loading, error, reload } = useApi(listSystemConfig, [])
  const [adding, setAdding] = useState(false)
  const [newForm, setNewForm] = useState(EMPTY)
  const [addError, setAddError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editingKey, setEditingKey] = useState(null)
  const [editForm, setEditForm] = useState(EMPTY)
  const [editError, setEditError] = useState(null)
  const [deletingKey, setDeletingKey] = useState(null)

  const items = data || []

  const startEdit = (c) => {
    setEditingKey(c.config_key)
    setEditForm({ config_value: c.config_value || '', value_type: c.value_type, description: c.description || '' })
    setEditError(null)
  }

  const submitNew = async (e) => {
    e.preventDefault()
    setAddError(null)
    setBusy(true)
    try {
      await createSystemConfig({
        config_key: newForm.config_key.trim(),
        config_value: newForm.config_value.trim() || undefined,
        value_type: newForm.value_type,
        description: newForm.description.trim() || undefined,
      })
      setNewForm(EMPTY)
      setAdding(false)
      reload()
    } catch (err) {
      setAddError(extractErrorMessage(err, 'Could not create this config key.'))
    } finally {
      setBusy(false)
    }
  }

  const submitEdit = async (key) => {
    setBusy(true)
    setEditError(null)
    try {
      await updateSystemConfig(key, {
        config_value: editForm.config_value.trim() || null,
        value_type: editForm.value_type,
        description: editForm.description.trim() || null,
      })
      setEditingKey(null)
      reload()
    } catch (err) {
      setEditError(extractErrorMessage(err, 'Could not update this config key.'))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (key) => {
    if (!window.confirm(`Delete config key "${key}"?`)) return
    setDeletingKey(key)
    try {
      await deleteSystemConfig(key)
      reload()
    } catch (err) {
      setEditError(extractErrorMessage(err, 'Could not delete this config key.'))
    } finally {
      setDeletingKey(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">Runtime tunables — e.g. stage1_threshold, stage3_combine_mode.</p>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200"
        >
          <PlusIcon className="h-4 w-4" />
          Add config key
        </button>
      </div>

      <ErrorBanner error={error} />

      {adding && (
        <form onSubmit={submitNew} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-4">
          <TextField label="Key" placeholder="stage1_threshold" value={newForm.config_key} onChange={(e) => setNewForm((f) => ({ ...f, config_key: e.target.value }))} />
          <TextField label="Value" placeholder="0.5" value={newForm.config_value} onChange={(e) => setNewForm((f) => ({ ...f, config_value: e.target.value }))} />
          <SelectField label="Type" value={newForm.value_type} onChange={(e) => setNewForm((f) => ({ ...f, value_type: e.target.value }))}>
            {CONFIG_VALUE_TYPES.map((t) => <option key={t} value={t} className="bg-white">{t}</option>)}
          </SelectField>
          <TextField label="Description" value={newForm.description} onChange={(e) => setNewForm((f) => ({ ...f, description: e.target.value }))} />
          <div className="sm:col-span-4 flex items-center gap-3">
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
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Key</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Value</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Type</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Description</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-500">No config keys set.</td></tr>
              )}
              {items.map((c) =>
                editingKey === c.config_key ? (
                  <tr key={c.id} className="bg-slate-50">
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{c.config_key}</td>
                    <td className="px-4 py-2.5">
                      <TextField value={editForm.config_value} onChange={(e) => setEditForm((f) => ({ ...f, config_value: e.target.value }))} />
                    </td>
                    <td className="px-4 py-2.5">
                      <SelectField value={editForm.value_type} onChange={(e) => setEditForm((f) => ({ ...f, value_type: e.target.value }))}>
                        {CONFIG_VALUE_TYPES.map((t) => <option key={t} value={t} className="bg-white">{t}</option>)}
                      </SelectField>
                    </td>
                    <td className="px-4 py-2.5">
                      <TextField value={editForm.description} onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} />
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => submitEdit(c.config_key)} disabled={busy} className="rounded-lg bg-sky-500 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-600 disabled:opacity-60">Save</button>
                        <button onClick={() => setEditingKey(null)} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100">Cancel</button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={c.id} className="transition-colors hover:bg-slate-100">
                    <td onClick={() => startEdit(c)} className="cursor-pointer px-4 py-2.5 font-mono text-xs text-slate-700">{c.config_key}</td>
                    <td onClick={() => startEdit(c)} className="cursor-pointer px-4 py-2.5 text-slate-700">{c.config_value ?? '—'}</td>
                    <td onClick={() => startEdit(c)} className="cursor-pointer px-4 py-2.5 text-slate-600">{c.value_type}</td>
                    <td onClick={() => startEdit(c)} className="cursor-pointer px-4 py-2.5 text-slate-500">{c.description || '—'}</td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => remove(c.config_key)}
                        disabled={deletingKey === c.config_key}
                        title="Delete"
                        className="rounded-lg p-1.5 text-slate-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                      >
                        {deletingKey === c.config_key ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <TrashIcon className="h-4 w-4" />}
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
