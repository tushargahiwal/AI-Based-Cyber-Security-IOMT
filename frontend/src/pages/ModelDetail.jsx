import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import { getModel, updateModel, activateModel, MODEL_TASK_TYPES, MODEL_STAGES } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import ModelEvaluation from '../components/ModelEvaluation'
import { TagIcon, CpuIcon, CheckCircleIcon, SpinnerIcon } from '../components/icons'

const EMPTY_FORM = {
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
}

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

export default function ModelDetail() {
  const { id } = useParams()
  const location = useLocation()
  const justCreated = location.state?.justCreated
  const { user } = useCurrentUser()
  const { data: model, loading, error, reload } = useApi(() => getModel(id), [id])

  const canEdit = hasPermission(user, 'models.retrain')
  const canActivate = hasPermission(user, 'models.activate')

  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [activating, setActivating] = useState(false)
  const [activateError, setActivateError] = useState(null)

  useEffect(() => {
    if (!model) return
    setForm({
      display_name: model.display_name || '',
      stage: model.stage ?? '',
      algorithm: model.algorithm || '',
      task_type: model.task_type || '',
      version: model.version,
      artifact_path: model.artifact_path,
      scaler_path: model.scaler_path || '',
      feature_set_version: model.feature_set_version || '',
      input_dim: model.input_dim ?? '',
      threshold: model.threshold ?? '',
    })
  }, [model])

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
      await updateModel(id, {
        display_name: form.display_name || null,
        stage: form.stage === '' ? null : Number(form.stage),
        algorithm: form.algorithm || null,
        task_type: form.task_type || null,
        version: form.version,
        artifact_path: form.artifact_path,
        scaler_path: form.scaler_path || null,
        feature_set_version: form.feature_set_version || null,
        input_dim: form.input_dim === '' ? null : Number(form.input_dim),
        threshold: form.threshold === '' ? null : Number(form.threshold),
      })
      setSaved(true)
      reload()
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Could not update this model.'))
    } finally {
      setSaving(false)
    }
  }

  const activate = async () => {
    setActivating(true)
    setActivateError(null)
    try {
      await activateModel(id)
      reload()
    } catch (err) {
      setActivateError(extractErrorMessage(err, 'Could not activate this model.'))
    } finally {
      setActivating(false)
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />

      {justCreated && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
          Model registered.
        </div>
      )}

      {model && (
        <>
          <Card title="Status">
            <div className="flex flex-wrap items-center gap-3">
              {model.is_active ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-sm text-emerald-700 ring-1 ring-inset ring-emerald-200">
                  <CheckCircleIcon className="h-4 w-4" />
                  Active {model.stage ? `for Stage ${model.stage}` : ''}
                </span>
              ) : (
                <span className="rounded-full bg-slate-100 px-3 py-1.5 text-sm text-slate-600 ring-1 ring-inset ring-slate-200">
                  Inactive
                </span>
              )}
              {canActivate && !model.is_active && (
                <button
                  type="button"
                  onClick={activate}
                  disabled={activating}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-100 px-3.5 py-2 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {activating && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                  Activate
                </button>
              )}
              {model.trained_by_username && (
                <span className="ml-auto text-sm text-slate-600">
                  Registered by <span className="font-medium text-slate-800">{model.trained_by_username}</span>
                </span>
              )}
            </div>
            {model.stage && model.is_active && (
              <p className="mt-3 text-xs text-slate-500">
                Activating a different model for Stage {model.stage} will automatically deactivate this one.
              </p>
            )}
            {activateError && <p className="mt-3 text-xs text-red-600">{activateError}</p>}
          </Card>

          <ModelEvaluation modelId={id} />

          <Card>
            <form onSubmit={submit} noValidate className="space-y-5">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TextField label="Model code" icon={TagIcon} value={model.model_code} disabled />
                <TextField label="Display name" icon={CpuIcon} value={form.display_name} onChange={set('display_name')} disabled={!canEdit} />
              </div>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
                <SelectField label="Stage" value={form.stage} onChange={set('stage')} disabled={!canEdit}>
                  <option value="" className="bg-white">—</option>
                  {MODEL_STAGES.map((s) => <option key={s} value={s} className="bg-white">Stage {s}</option>)}
                </SelectField>
                <SelectField label="Task type" value={form.task_type} onChange={set('task_type')} disabled={!canEdit}>
                  <option value="" className="bg-white">—</option>
                  {MODEL_TASK_TYPES.map((t) => <option key={t} value={t} className="bg-white">{t}</option>)}
                </SelectField>
                <TextField label="Algorithm" value={form.algorithm} onChange={set('algorithm')} disabled={!canEdit} />
              </div>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TextField label="Version" value={form.version} onChange={set('version')} disabled={!canEdit} />
                <TextField label="Feature set version" value={form.feature_set_version} onChange={set('feature_set_version')} disabled={!canEdit} />
              </div>

              <TextField label="Artifact path" value={form.artifact_path} onChange={set('artifact_path')} disabled={!canEdit} />
              <TextField label="Scaler path" value={form.scaler_path} onChange={set('scaler_path')} disabled={!canEdit} />

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TextField label="Input dim" type="number" value={form.input_dim} onChange={set('input_dim')} disabled={!canEdit} />
                <TextField label="Decision threshold" type="number" step="0.0001" value={form.threshold} onChange={set('threshold')} disabled={!canEdit} />
              </div>

              {saveError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {saveError}
                </div>
              )}
              {saved && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
                  Model updated.
                </div>
              )}

              {canEdit && (
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
        </>
      )}

      {loading && !model && <p className="text-sm text-slate-500">Loading model…</p>}
    </div>
  )
}
