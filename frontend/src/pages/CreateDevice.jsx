import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useApi from '../hooks/useApi'
import { createDevice, listDeviceTypes, listWards } from '../api/client'
import { extractErrorMessage, errorStatus } from '../api/errors'
import Card from '../components/Card'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import { TagIcon, MonitorIcon, MapPinIcon, BuildingIcon, FirmwareIcon, SpinnerIcon } from '../components/icons'

const MAC_PATTERN = /^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/
const IP_PATTERN = /^(\d{1,3}\.){3}\d{1,3}$/

const initialForm = {
  device_uid: '',
  device_type: '',
  ward: '',
  manufacturer: '',
  model_number: '',
  firmware_version: '',
  ip_address: '',
  mac_address: '',
  mqtt_client_id: '',
}

export default function CreateDevice() {
  const navigate = useNavigate()
  const { data: deviceTypes } = useApi(listDeviceTypes, [])
  const { data: wards } = useApi(listWards, [])

  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const validate = () => {
    const next = {}
    if (!form.device_uid.trim()) next.device_uid = 'Device ID is required.'
    if (!form.device_type) next.device_type = 'Select a device type.'
    if (form.ip_address.trim() && !IP_PATTERN.test(form.ip_address.trim()))
      next.ip_address = 'Enter a valid IPv4 address.'
    if (form.mac_address.trim() && !MAC_PATTERN.test(form.mac_address.trim()))
      next.mac_address = 'Format: AA:BB:CC:DD:EE:FF'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async (e) => {
    e.preventDefault()
    setFormError(null)
    if (!validate()) return

    setBusy(true)
    try {
      const { data } = await createDevice({
        device_uid: form.device_uid.trim(),
        device_type: form.device_type,
        ward: form.ward || undefined,
        manufacturer: form.manufacturer.trim() || undefined,
        model_number: form.model_number.trim() || undefined,
        firmware_version: form.firmware_version.trim() || undefined,
        ip_address: form.ip_address.trim() || undefined,
        mac_address: form.mac_address.trim() || undefined,
        mqtt_client_id: form.mqtt_client_id.trim() || undefined,
      })
      navigate(`/devices/${data.id}`, { state: { justCreated: true } })
    } catch (err) {
      if (errorStatus(err) === 409) {
        setFormError('That device ID or MAC address is already registered.')
      } else {
        setFormError(extractErrorMessage(err, 'Could not register this device.'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <form onSubmit={submit} noValidate className="space-y-5">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label="Device ID"
              icon={TagIcon}
              placeholder="MON-ICU1-003"
              autoFocus
              value={form.device_uid}
              onChange={set('device_uid')}
              error={errors.device_uid}
            />
            <SelectField label="Device type" icon={MonitorIcon} value={form.device_type} onChange={set('device_type')} error={errors.device_type}>
              <option value="" className="bg-white text-slate-500">Select a type…</option>
              {(deviceTypes || []).map((dt) => (
                <option key={dt.id} value={dt.type_name} className="bg-white text-slate-900">
                  {dt.type_name}{dt.is_life_critical ? ' (life-critical)' : ''}
                </option>
              ))}
            </SelectField>
          </div>

          <SelectField label="Ward" icon={MapPinIcon} value={form.ward} onChange={set('ward')}>
            <option value="" className="bg-white text-slate-500">Unassigned</option>
            {(wards || []).map((w) => (
              <option key={w.id} value={w.name} className="bg-white text-slate-900">{w.name}</option>
            ))}
          </SelectField>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label="Manufacturer"
              icon={BuildingIcon}
              placeholder="Philips"
              value={form.manufacturer}
              onChange={set('manufacturer')}
            />
            <TextField
              label="Model number"
              placeholder="IntelliVue MX450"
              value={form.model_number}
              onChange={set('model_number')}
            />
          </div>

          <TextField
            label="Firmware version"
            icon={FirmwareIcon}
            placeholder="v3.2.1"
            value={form.firmware_version}
            onChange={set('firmware_version')}
          />

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label="IP address"
              placeholder="192.168.20.11"
              value={form.ip_address}
              onChange={set('ip_address')}
              error={errors.ip_address}
            />
            <TextField
              label="MAC address"
              placeholder="AA:BB:CC:DD:EE:FF"
              value={form.mac_address}
              onChange={set('mac_address')}
              error={errors.mac_address}
            />
          </div>

          <TextField
            label="MQTT client ID"
            placeholder="mon-icu1-003"
            value={form.mqtt_client_id}
            onChange={set('mqtt_client_id')}
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
            {busy ? 'Registering…' : 'Register device'}
          </button>
        </form>
      </Card>
    </div>
  )
}
