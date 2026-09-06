import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useApi from '../hooks/useApi'
import { createPatient, listWards, PATIENT_SEXES } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import { HeartPulseIcon, MapPinIcon, SpinnerIcon } from '../components/icons'

const AGE_BAND_PATTERN = /^\d{1,3}-\d{1,3}$/

const initialForm = {
  age_band: '',
  sex: 'U',
  ward: '',
  baseline_hr_min: '',
  baseline_hr_max: '',
  baseline_spo2_min: '',
  notes: '',
}

export default function CreatePatient() {
  const navigate = useNavigate()
  const { data: wards } = useApi(listWards, [])

  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const validate = () => {
    const next = {}
    if (form.age_band.trim() && !AGE_BAND_PATTERN.test(form.age_band.trim()))
      next.age_band = "Use a band like '30-39', not an exact age."
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async (e) => {
    e.preventDefault()
    setFormError(null)
    if (!validate()) return

    setBusy(true)
    try {
      const { data } = await createPatient({
        age_band: form.age_band.trim() || undefined,
        sex: form.sex,
        ward: form.ward || undefined,
        baseline_hr_min: form.baseline_hr_min ? Number(form.baseline_hr_min) : undefined,
        baseline_hr_max: form.baseline_hr_max ? Number(form.baseline_hr_max) : undefined,
        baseline_spo2_min: form.baseline_spo2_min ? Number(form.baseline_spo2_min) : undefined,
        notes: form.notes.trim() || undefined,
      })
      navigate(`/patients/${data.id}`, { state: { justCreated: true } })
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not admit this patient.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <p className="mb-5 text-xs text-slate-500">
          Patients are pseudonymised — a patient code (e.g. PT-0001) is assigned automatically. No name or exact
          date of birth is stored.
        </p>
        <form onSubmit={submit} noValidate className="space-y-5">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label="Age band"
              icon={HeartPulseIcon}
              placeholder="30-39"
              autoFocus
              value={form.age_band}
              onChange={set('age_band')}
              error={errors.age_band}
              hint="Banded, not exact — e.g. 30-39"
            />
            <SelectField label="Sex" value={form.sex} onChange={set('sex')}>
              {PATIENT_SEXES.map((s) => (
                <option key={s.value} value={s.value} className="bg-white text-slate-900">{s.label}</option>
              ))}
            </SelectField>
          </div>

          <SelectField label="Ward" icon={MapPinIcon} value={form.ward} onChange={set('ward')}>
            <option value="" className="bg-white text-slate-500">Unassigned</option>
            {(wards || []).map((w) => (
              <option key={w.id} value={w.name} className="bg-white text-slate-900">{w.name}</option>
            ))}
          </SelectField>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
            <TextField
              label="Baseline HR min"
              type="number"
              placeholder="60"
              value={form.baseline_hr_min}
              onChange={set('baseline_hr_min')}
            />
            <TextField
              label="Baseline HR max"
              type="number"
              placeholder="100"
              value={form.baseline_hr_max}
              onChange={set('baseline_hr_max')}
            />
            <TextField
              label="Baseline SpO2 min"
              type="number"
              placeholder="95"
              value={form.baseline_spo2_min}
              onChange={set('baseline_spo2_min')}
            />
          </div>

          <TextField
            label="Notes"
            placeholder="No clinical detail — general context only"
            value={form.notes}
            onChange={set('notes')}
          />

          {formError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
              {formError}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
            {busy ? 'Admitting…' : 'Admit patient'}
          </button>
        </form>
      </Card>
    </div>
  )
}
