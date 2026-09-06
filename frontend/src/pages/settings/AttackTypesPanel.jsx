import { useState } from 'react'
import useApi from '../../hooks/useApi'
import { listAttackTypes, createAttackType, updateAttackType, ATTACK_FAMILIES } from '../../api/client'
import { extractErrorMessage } from '../../api/errors'
import ErrorBanner from '../../components/ErrorBanner'
import TextField from '../../components/TextField'
import SelectField from '../../components/SelectField'
import { PlusIcon, SpinnerIcon } from '../../components/icons'

const SEVERITIES = ['info', 'low', 'medium', 'high', 'critical']

const EMPTY = { code: '', family: 'UNKNOWN', display_name: '', default_severity: '', mitre_technique: '' }

export default function AttackTypesPanel() {
  const { data, loading, error, reload } = useApi(listAttackTypes, [])
  const [adding, setAdding] = useState(false)
  const [newForm, setNewForm] = useState(EMPTY)
  const [addError, setAddError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(EMPTY)
  const [editError, setEditError] = useState(null)

  const items = data || []

  const startEdit = (a) => {
    setEditingId(a.id)
    setEditForm({
      code: a.code,
      family: a.family,
      display_name: a.display_name || '',
      default_severity: a.default_severity || '',
      mitre_technique: a.mitre_technique || '',
    })
    setEditError(null)
  }

  const submitNew = async (e) => {
    e.preventDefault()
    setAddError(null)
    setBusy(true)
    try {
      await createAttackType({
        code: newForm.code.trim(),
        family: newForm.family,
        display_name: newForm.display_name.trim() || undefined,
        default_severity: newForm.default_severity || undefined,
        mitre_technique: newForm.mitre_technique.trim() || undefined,
      })
      setNewForm(EMPTY)
      setAdding(false)
      reload()
    } catch (err) {
      setAddError(extractErrorMessage(err, 'Could not create this attack type.'))
    } finally {
      setBusy(false)
    }
  }

  const submitEdit = async (id) => {
    setBusy(true)
    setEditError(null)
    try {
      await updateAttackType(id, {
        family: editForm.family,
        display_name: editForm.display_name.trim() || null,
        default_severity: editForm.default_severity || null,
        mitre_technique: editForm.mitre_technique.trim() || null,
      })
      setEditingId(null)
      reload()
    } catch (err) {
      setEditError(extractErrorMessage(err, 'Could not update this attack type.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">Attack taxonomy — MITRE mapping and default severities.</p>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200"
        >
          <PlusIcon className="h-4 w-4" />
          Add attack type
        </button>
      </div>

      <ErrorBanner error={error} />

      {adding && (
        <form onSubmit={submitNew} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-5">
          <TextField label="Code" placeholder="DDOS_ICMP_FLOOD" value={newForm.code} onChange={(e) => setNewForm((f) => ({ ...f, code: e.target.value }))} />
          <SelectField label="Family" value={newForm.family} onChange={(e) => setNewForm((f) => ({ ...f, family: e.target.value }))}>
            {ATTACK_FAMILIES.map((fam) => <option key={fam} value={fam} className="bg-white">{fam}</option>)}
          </SelectField>
          <TextField label="Display name" placeholder="ICMP Flood (DDoS)" value={newForm.display_name} onChange={(e) => setNewForm((f) => ({ ...f, display_name: e.target.value }))} />
          <SelectField label="Default severity" value={newForm.default_severity} onChange={(e) => setNewForm((f) => ({ ...f, default_severity: e.target.value }))}>
            <option value="" className="bg-white">—</option>
            {SEVERITIES.map((s) => <option key={s} value={s} className="bg-white capitalize">{s}</option>)}
          </SelectField>
          <TextField label="MITRE technique" placeholder="T1498" value={newForm.mitre_technique} onChange={(e) => setNewForm((f) => ({ ...f, mitre_technique: e.target.value }))} />
          <div className="sm:col-span-5 flex items-center gap-3">
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
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Code</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Family</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Display name</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Severity</th>
                <th className="px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">MITRE</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">No attack types defined.</td></tr>
              )}
              {items.map((a) =>
                editingId === a.id ? (
                  <tr key={a.id} className="bg-slate-50">
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{a.code}</td>
                    <td className="px-4 py-2.5">
                      <SelectField value={editForm.family} onChange={(e) => setEditForm((f) => ({ ...f, family: e.target.value }))}>
                        {ATTACK_FAMILIES.map((fam) => <option key={fam} value={fam} className="bg-white">{fam}</option>)}
                      </SelectField>
                    </td>
                    <td className="px-4 py-2.5">
                      <TextField value={editForm.display_name} onChange={(e) => setEditForm((f) => ({ ...f, display_name: e.target.value }))} />
                    </td>
                    <td className="px-4 py-2.5">
                      <SelectField value={editForm.default_severity} onChange={(e) => setEditForm((f) => ({ ...f, default_severity: e.target.value }))}>
                        <option value="" className="bg-white">—</option>
                        {SEVERITIES.map((s) => <option key={s} value={s} className="bg-white capitalize">{s}</option>)}
                      </SelectField>
                    </td>
                    <td className="px-4 py-2.5">
                      <TextField value={editForm.mitre_technique} onChange={(e) => setEditForm((f) => ({ ...f, mitre_technique: e.target.value }))} />
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button onClick={() => submitEdit(a.id)} disabled={busy} className="rounded-lg bg-sky-500 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-600 disabled:opacity-60">Save</button>
                        <button onClick={() => setEditingId(null)} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100">Cancel</button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={a.id} onClick={() => startEdit(a)} className="cursor-pointer transition-colors hover:bg-slate-100">
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-700">{a.code}</td>
                    <td className="px-4 py-2.5 text-slate-600">{a.family}</td>
                    <td className="px-4 py-2.5 text-slate-700">{a.display_name || '—'}</td>
                    <td className="px-4 py-2.5 text-slate-600 capitalize">{a.default_severity || '—'}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{a.mitre_technique || '—'}</td>
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
