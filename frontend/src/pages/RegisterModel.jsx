import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { registerModel, MODEL_TASK_TYPES, MODEL_STAGES } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import { TagIcon, CpuIcon, SpinnerIcon } from '../components/icons'

const initialForm = {
  model_code: '',
  display_name: '',
  stage: '',
  algorithm: '',
  task_type: '',
  version: '',
  artifact_path: '',
  scaler_path: '',
  feature_set_version: '',
  input_dim: '',
  threshold: '',
  hyperparameters: '',
}

export default function RegisterModel() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const validate = () => {
    const next = {}
    if (!form.model_code.trim()) next.model_code = 'Model code is required.'
    if (!form.version.trim()) next.version = 'Version is required.'
    if (!form.artifact_path.trim()) next.artifact_path = 'Artifact path is required.'
    if (form.hyperparameters.trim()) {
      try {
        JSON.parse(form.hyperparameters)
      } catch {
        next.hyperparameters = 'Must be valid JSON.'
      }
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async (e) => {
    e.preventDefault()
    setFormError(null)
    if (!validate()) return

    setBusy(true)
    try {
      const { data } = await registerModel({
        model_code: form.model_code.trim(),
        display_name: form.display_name.trim() || undefined,
        stage: form.stage ? Number(form.stage) : undefined,
        algorithm: form.algorithm.trim() || undefined,
        task_type: form.task_type || undefined,
        version: form.version.trim(),
        artifact_path: form.artifact_path.trim(),
        scaler_path: form.scaler_path.trim() || undefined,
        feature_set_version: form.feature_set_version.trim() || undefined,
        input_dim: form.input_dim ? Number(form.input_dim) : undefined,
        threshold: form.threshold ? Number(form.threshold) : undefined,
        hyperparameters: form.hyperparameters.trim() ? JSON.parse(form.hyperparameters) : undefined,
      })
      navigate(`/models/${data.id}`, { state: { justCreated: true } })
    } catch (err) {
      if (err?.response?.status === 409) {
        setFormError('That model code is already registered.')
      } else {
        setFormError(extractErrorMessage(err, 'Could not register this model.'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <p className="mb-5 text-xs text-slate-500">
          Register a model that was trained offline (Jupyter/Colab) and its artifact saved to disk — this records
          it in the registry, it doesn't run training here.
        </p>
        <form onSubmit={submit} noValidate className="space-y-5">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label="Model code"
              icon={TagIcon}
              placeholder="M1_RF_BINARY"
              autoFocus
              value={form.model_code}
              onChange={set('model_code')}
              error={errors.model_code}
            />
            <TextField
              label="Display name"
              icon={CpuIcon}
              placeholder="Random Forest (Binary)"
              value={form.display_name}
              onChange={set('display_name')}
            />
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
            <SelectField label="Stage" value={form.stage} onChange={set('stage')}>
              <option value="" className="bg-white">—</option>
              {MODEL_STAGES.map((s) => <option key={s} value={s} className="bg-white">Stage {s}</option>)}
            </SelectField>
            <SelectField label="Task type" value={form.task_type} onChange={set('task_type')}>
              <option value="" className="bg-white">—</option>
              {MODEL_TASK_TYPES.map((t) => <option key={t} value={t} className="bg-white">{t}</option>)}
            </SelectField>
            <TextField label="Algorithm" placeholder="RandomForest" value={form.algorithm} onChange={set('algorithm')} />
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField label="Version" placeholder="v1.0.0" value={form.version} onChange={set('version')} error={errors.version} />
            <TextField label="Feature set version" placeholder="v1" value={form.feature_set_version} onChange={set('feature_set_version')} />
          </div>

          <TextField
            label="Artifact path"
            placeholder="models/binary_rf_v1.pkl"
            value={form.artifact_path}
            onChange={set('artifact_path')}
            error={errors.artifact_path}
          />
          <TextField
            label="Scaler path"
            placeholder="models/scaler_v1.pkl"
            value={form.scaler_path}
            onChange={set('scaler_path')}
          />

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField label="Input dim" type="number" value={form.input_dim} onChange={set('input_dim')} />
            <TextField label="Decision threshold" type="number" step="0.0001" placeholder="0.5" value={form.threshold} onChange={set('threshold')} />
          </div>

          <TextField
            label="Hyperparameters (JSON)"
            placeholder='{"n_estimators": 200, "max_depth": 25}'
            value={form.hyperparameters}
            onChange={set('hyperparameters')}
            error={errors.hyperparameters}
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
            {busy ? 'Registering…' : 'Register model'}
          </button>
        </form>
      </Card>
    </div>
  )
}
