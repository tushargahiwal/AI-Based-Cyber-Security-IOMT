import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import {
  getPatient,
  updatePatient,
  listPatientAssignments,
  assignDeviceToPatient,
  releaseAssignment,
  listDevices,
  listWards,
  PATIENT_SEXES,
} from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import { HeartPulseIcon, MapPinIcon, MonitorIcon, LinkIcon, SpinnerIcon } from '../components/icons'

const EMPTY_FORM = {
  age_band: '',
  sex: 'U',
  ward: '',
  baseline_hr_min: '',
  baseline_hr_max: '',
  baseline_spo2_min: '',
  notes: '',
}

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

export default function PatientDetail() {
  const { id } = useParams()
  const location = useLocation()
  const justCreated = location.state?.justCreated
  const { user } = useCurrentUser()
  const { data: patient, loading, error, reload } = useApi(() => getPatient(id), [id])
  const { data: assignments, reload: reloadAssignments } = useApi(() => listPatientAssignments(id), [id])
  const { data: wards } = useApi(listWards, [])
  const { data: deviceOptions } = useApi(() => listDevices({ page: 1, size: 100 }), [])

  const canWrite = hasPermission(user, 'patients.write')

  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(false)

  const [dischargeBusy, setDischargeBusy] = useState(false)

  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  const [assignBusy, setAssignBusy] = useState(false)
  const [assignError, setAssignError] = useState(null)
  const [releasingId, setReleasingId] = useState(null)

  useEffect(() => {
    if (!patient) return
    setForm({
      age_band: patient.age_band || '',
      sex: patient.sex || 'U',
      ward: patient.ward?.name || '',
      baseline_hr_min: patient.baseline_hr_min ?? '',
      baseline_hr_max: patient.baseline_hr_max ?? '',
      baseline_spo2_min: patient.baseline_spo2_min ?? '',
      notes: patient.notes || '',
    })
  }, [patient])

  const set = (key) => (e) => {
    setSaved(false)
    setForm((f) => ({ ...f, [key]: e.target.value }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      await updatePatient(id, {
        age_band: form.age_band || null,
        sex: form.sex,
        ward: form.ward || null,
        baseline_hr_min: form.baseline_hr_min === '' ? null : Number(form.baseline_hr_min),
        baseline_hr_max: form.baseline_hr_max === '' ? null : Number(form.baseline_hr_max),
        baseline_spo2_min: form.baseline_spo2_min === '' ? null : Number(form.baseline_spo2_min),
        notes: form.notes || null,
      })
      setSaved(true)
      reload()
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Could not update this patient.'))
    } finally {
      setSaving(false)
    }
  }

  const toggleDischarge = async () => {
    setDischargeBusy(true)
    try {
      await updatePatient(id, { discharged: !patient.discharged_at })
      reload()
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Could not change discharge status.'))
    } finally {
      setDischargeBusy(false)
    }
  }

  const assignDevice = async () => {
    if (!selectedDeviceId) return
    setAssignBusy(true)
    setAssignError(null)
    try {
      await assignDeviceToPatient(id, Number(selectedDeviceId))
      setSelectedDeviceId('')
      reloadAssignments()
    } catch (err) {
      setAssignError(extractErrorMessage(err, 'Could not assign this device.'))
    } finally {
      setAssignBusy(false)
    }
  }

  const release = async (assignmentId) => {
    setReleasingId(assignmentId)
    setAssignError(null)
    try {
      await releaseAssignment(id, assignmentId)
      reloadAssignments()
    } catch (err) {
      setAssignError(extractErrorMessage(err, 'Could not release this device.'))
    } finally {
      setReleasingId(null)
    }
  }

  const activeAssignments = (assignments || []).filter((a) => !a.released_at)
  const pastAssignments = (assignments || []).filter((a) => a.released_at)

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />

      {justCreated && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
          Patient admitted.
        </div>
      )}

      {patient && (
        <>
          <Card title="Status">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm ring-1 ring-inset ${
                  patient.discharged_at
                    ? 'bg-slate-100 text-slate-600 ring-slate-200'
                    : 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                }`}
              >
                {patient.discharged_at ? 'Discharged' : 'Admitted'}
              </span>
              {canWrite && (
                <button
                  type="button"
                  onClick={toggleDischarge}
                  disabled={dischargeBusy}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-100 px-3.5 py-2 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {dischargeBusy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                  {patient.discharged_at ? 'Re-admit' : 'Discharge'}
                </button>
              )}
            </div>
          </Card>

          <Card title="Profile">
            <form onSubmit={submit} noValidate className="space-y-5">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TextField label="Patient code" icon={HeartPulseIcon} value={patient.patient_code} disabled />
                <SelectField label="Sex" value={form.sex} onChange={set('sex')} disabled={!canWrite}>
                  {PATIENT_SEXES.map((s) => (
                    <option key={s.value} value={s.value} className="bg-white text-slate-900">{s.label}</option>
                  ))}
                </SelectField>
              </div>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TextField label="Age band" placeholder="30-39" value={form.age_band} onChange={set('age_band')} disabled={!canWrite} />
                <SelectField label="Ward" icon={MapPinIcon} value={form.ward} onChange={set('ward')} disabled={!canWrite}>
                  <option value="" className="bg-white text-slate-500">Unassigned</option>
                  {(wards || []).map((w) => (
                    <option key={w.id} value={w.name} className="bg-white text-slate-900">{w.name}</option>
                  ))}
                </SelectField>
              </div>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
                <TextField label="Baseline HR min" type="number" value={form.baseline_hr_min} onChange={set('baseline_hr_min')} disabled={!canWrite} />
                <TextField label="Baseline HR max" type="number" value={form.baseline_hr_max} onChange={set('baseline_hr_max')} disabled={!canWrite} />
                <TextField label="Baseline SpO2 min" type="number" value={form.baseline_spo2_min} onChange={set('baseline_spo2_min')} disabled={!canWrite} />
              </div>

              <TextField label="Notes" value={form.notes} onChange={set('notes')} disabled={!canWrite} />

              {saveError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {saveError}
                </div>
              )}
              {saved && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
                  Patient updated.
                </div>
              )}

              {canWrite && (
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
              )}
            </form>
          </Card>

          <Card title="Assigned devices">
            {canWrite && (
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <SelectField
                  value={selectedDeviceId}
                  onChange={(e) => setSelectedDeviceId(e.target.value)}
                  className="min-w-[14rem]"
                >
                  <option value="" className="bg-white text-slate-500">Select a device…</option>
                  {(deviceOptions?.items || []).map((d) => (
                    <option key={d.id} value={d.id} className="bg-white text-slate-900">
                      {d.device_uid} ({d.device_type.type_name})
                    </option>
                  ))}
                </SelectField>
                <button
                  type="button"
                  onClick={assignDevice}
                  disabled={!selectedDeviceId || assignBusy}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-100 px-3.5 py-2 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {assignBusy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                  <LinkIcon className="h-4 w-4" />
                  Assign
                </button>
              </div>
            )}
            {assignError && <p className="mb-4 text-xs text-red-600">{assignError}</p>}

            <div className="space-y-2">
              {activeAssignments.length === 0 && pastAssignments.length === 0 && (
                <p className="text-sm text-slate-500">No devices assigned yet.</p>
              )}
              {activeAssignments.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-2.5"
                >
                  <span className="flex items-center gap-2 text-sm text-slate-800">
                    <MonitorIcon className="h-4 w-4 text-slate-500" />
                    {a.device_uid || `Device #${a.device_id}`}
                    <span className="text-xs text-emerald-700">· active</span>
                  </span>
                  {canWrite && (
                    <button
                      type="button"
                      onClick={() => release(a.id)}
                      disabled={releasingId === a.id}
                      className="rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                    >
                      {releasingId === a.id ? 'Releasing…' : 'Release'}
                    </button>
                  )}
                </div>
              ))}
              {pastAssignments.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3.5 py-2.5 opacity-60"
                >
                  <span className="flex items-center gap-2 text-sm text-slate-600">
                    <MonitorIcon className="h-4 w-4 text-slate-600" />
                    {a.device_uid || `Device #${a.device_id}`}
                  </span>
                  <span className="text-xs text-slate-500">released</span>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}

      {loading && !patient && <p className="text-sm text-slate-500">Loading patient…</p>}
    </div>
  )
}
