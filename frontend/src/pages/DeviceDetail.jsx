import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import {
  getDevice,
  updateDevice,
  listDeviceTypes,
  listWards,
  listVitals,
  DEVICE_STATUSES,
  VITAL_FIELDS,
} from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import VitalsChart from '../components/VitalsChart'
import {
  TagIcon,
  MonitorIcon,
  MapPinIcon,
  BuildingIcon,
  FirmwareIcon,
  SpinnerIcon,
  HeartPulseIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
} from '../components/icons'

const EMPTY_FORM = {
  device_type: '',
  ward: '',
  manufacturer: '',
  model_number: '',
  firmware_version: '',
  ip_address: '',
  mac_address: '',
  mqtt_client_id: '',
}

const STATUS_STYLES = {
  online: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  offline: 'bg-slate-100 text-slate-600 ring-slate-200',
  quarantined: 'bg-red-50 text-red-700 ring-red-200',
  maintenance: 'bg-amber-50 text-amber-700 ring-amber-200',
}

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

function VitalsCard({ readings }) {
  const latest = readings[0]
  const scored = readings.filter((r) => r.stage4_evaluated)
  const predicted = latest.predicted_values?.predicted

  return (
    <Card title="Vitals — Stage 4 plausibility">
      <div className="flex flex-wrap items-center gap-3">
        <HeartPulseIcon className="h-4 w-4 text-slate-500" />
        {latest.stage4_evaluated ? (
          latest.injection_suspected ? (
            <span className="flex items-center gap-2 text-sm text-purple-700">
              <AlertTriangleIcon className="h-3.5 w-3.5" />
              Latest reading implausible — {Number(latest.residual_zscore).toFixed(2)}σ off forecast
            </span>
          ) : (
            <span className="flex items-center gap-2 text-sm text-emerald-700">
              <CheckCircleIcon className="h-3.5 w-3.5" />
              Latest reading consistent — {Number(latest.residual_zscore).toFixed(2)}σ off forecast
            </span>
          )
        ) : (
          <span className="text-sm text-slate-600">
            Not yet scored — Stage 4 needs 31 consecutive readings from this device.
          </span>
        )}
        <span className="ml-auto text-xs text-slate-500">
          {new Date(latest.recorded_at).toLocaleString()}
        </span>
      </div>

      <div className="mt-6">
        <VitalsChart readings={readings} />
      </div>

      <div className="mt-6 overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <th className="pb-2">Vital</th>
              <th className="pb-2">Reported</th>
              <th className="pb-2">Forecast</th>
            </tr>
          </thead>
          <tbody className="text-slate-800">
            {VITAL_FIELDS.map((f) => {
              const reported = latest[f.key]
              const forecast = predicted?.[f.modelKey]
              return (
                <tr key={f.key} className="border-t border-slate-100">
                  <td className="py-2 text-slate-600">{f.label}</td>
                  <td className="py-2">{reported != null ? `${reported} ${f.unit}` : '—'}</td>
                  <td className="py-2 text-slate-600">
                    {forecast != null ? `${forecast.toFixed(1)} ${f.unit}` : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-xs text-slate-500">
        The table shows the most recent of {readings.length} readings ({scored.length} scored by Stage 4).
        The forecast is what an LSTM trained on benign vitals expected next, given this device's previous
        30 readings.
      </p>
    </Card>
  )
}

export default function DeviceDetail() {
  const { id } = useParams()
  const location = useLocation()
  const justCreated = location.state?.justCreated
  const { user } = useCurrentUser()
  const { data: device, loading, error, reload } = useApi(() => getDevice(id), [id])
  const { data: deviceTypes } = useApi(listDeviceTypes, [])
  const { data: wards } = useApi(listWards, [])
  // Only clinicians and above hold vitals.read; for everyone else the request
  // 403s and the section simply stays hidden.
  const canReadVitals = hasPermission(user, 'vitals.read')
  const { data: vitals } = useApi(
    () => (canReadVitals ? listVitals({ device_id: id, size: 120 }) : Promise.resolve({ data: null })),
    [id, canReadVitals],
  )

  const canWrite = hasPermission(user, 'devices.write')
  const canQuarantine = canWrite || hasPermission(user, 'devices.quarantine')

  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(false)

  const [statusValue, setStatusValue] = useState('')
  const [statusSaving, setStatusSaving] = useState(false)
  const [statusError, setStatusError] = useState(null)

  useEffect(() => {
    if (!device) return
    setForm({
      device_type: device.device_type.type_name,
      ward: device.ward?.name || '',
      manufacturer: device.manufacturer || '',
      model_number: device.model_number || '',
      firmware_version: device.firmware_version || '',
      ip_address: device.ip_address || '',
      mac_address: device.mac_address || '',
      mqtt_client_id: device.mqtt_client_id || '',
    })
    setStatusValue(device.status)
  }, [device])

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
      await updateDevice(id, { ...form, ward: form.ward || null })
      setSaved(true)
      reload()
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Could not update this device.'))
    } finally {
      setSaving(false)
    }
  }

  const submitStatus = async () => {
    setStatusSaving(true)
    setStatusError(null)
    try {
      await updateDevice(id, { status: statusValue })
      reload()
    } catch (err) {
      setStatusError(extractErrorMessage(err, 'Could not change the device status.'))
    } finally {
      setStatusSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />

      {justCreated && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
          Device registered.
        </div>
      )}

      {device && (
        <>
          <Card title="Status">
            {device.device_type.is_life_critical && (
              <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-700">
                Life-critical device — never auto-disconnected. Status changes here are manual, operator-initiated actions only.
              </div>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm capitalize ring-1 ring-inset ${STATUS_STYLES[device.status]}`}
              >
                {device.status}
              </span>

              {canQuarantine && (
                <>
                  <SelectField
                    value={statusValue}
                    onChange={(e) => setStatusValue(e.target.value)}
                    className="min-w-[9rem]"
                  >
                    {DEVICE_STATUSES.map((s) => (
                      <option key={s} value={s} className="bg-white capitalize">{s}</option>
                    ))}
                  </SelectField>
                  <button
                    type="button"
                    onClick={submitStatus}
                    disabled={statusSaving || statusValue === device.status}
                    className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-100 px-3.5 py-2 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {statusSaving && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                    Update status
                  </button>
                </>
              )}

              <span className="ml-auto text-sm text-slate-600">
                Trust score: <span className="font-medium text-slate-800">{device.trust_score.toFixed(0)}</span>
              </span>
            </div>
            {statusError && <p className="mt-3 text-xs text-red-600">{statusError}</p>}
          </Card>

          {canReadVitals && vitals?.items?.length > 0 && <VitalsCard readings={vitals.items} />}

          <Card>
            <form onSubmit={submit} noValidate className="space-y-5">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TextField label="Device ID" icon={TagIcon} value={device.device_uid} disabled />
                <SelectField
                  label="Device type"
                  icon={MonitorIcon}
                  value={form.device_type}
                  onChange={set('device_type')}
                  disabled={!canWrite}
                >
                  {(deviceTypes || []).map((dt) => (
                    <option key={dt.id} value={dt.type_name} className="bg-white text-slate-900">
                      {dt.type_name}
                    </option>
                  ))}
                </SelectField>
              </div>

              <SelectField label="Ward" icon={MapPinIcon} value={form.ward} onChange={set('ward')} disabled={!canWrite}>
                <option value="" className="bg-white text-slate-500">Unassigned</option>
                {(wards || []).map((w) => (
                  <option key={w.id} value={w.name} className="bg-white text-slate-900">{w.name}</option>
                ))}
              </SelectField>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TextField
                  label="Manufacturer"
                  icon={BuildingIcon}
                  value={form.manufacturer}
                  onChange={set('manufacturer')}
                  disabled={!canWrite}
                />
                <TextField
                  label="Model number"
                  value={form.model_number}
                  onChange={set('model_number')}
                  disabled={!canWrite}
                />
              </div>

              <TextField
                label="Firmware version"
                icon={FirmwareIcon}
                value={form.firmware_version}
                onChange={set('firmware_version')}
                disabled={!canWrite}
              />

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <TextField label="IP address" value={form.ip_address} onChange={set('ip_address')} disabled={!canWrite} />
                <TextField label="MAC address" value={form.mac_address} onChange={set('mac_address')} disabled={!canWrite} />
              </div>

              <TextField
                label="MQTT client ID"
                value={form.mqtt_client_id}
                onChange={set('mqtt_client_id')}
                disabled={!canWrite}
              />

              {saveError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {saveError}
                </div>
              )}
              {saved && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
                  Device updated.
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
        </>
      )}

      {loading && !device && <p className="text-sm text-slate-500">Loading device…</p>}
    </div>
  )
}
