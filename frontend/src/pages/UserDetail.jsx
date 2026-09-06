import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import useApi from '../hooks/useApi'
import { getUser, updateUser, REGISTERABLE_ROLES } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import { UserIcon, MailIcon, BuildingIcon, PhoneIcon, MapPinIcon, ShieldIcon, SpinnerIcon } from '../components/icons'

const EMPTY_FORM = {
  full_name: '',
  email: '',
  department: '',
  mobile: '',
  address: '',
  city: '',
  state: '',
  role: 'viewer',
  is_active: true,
}

export default function UserDetail() {
  const { id } = useParams()
  const location = useLocation()
  const justCreated = location.state?.justCreated
  const { data: user, loading, error, reload } = useApi(() => getUser(id), [id])
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!user) return
    setForm({
      full_name: user.full_name || '',
      email: user.email || '',
      department: user.department || '',
      mobile: user.mobile || '',
      address: user.address || '',
      city: user.city || '',
      state: user.state || '',
      role: user.role,
      is_active: user.is_active,
    })
  }, [user])

  const set = (key) => (e) => {
    setSaved(false)
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [key]: value }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      await updateUser(id, form)
      setSaved(true)
      reload()
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Could not update this user.'))
    } finally {
      setSaving(false)
    }
  }

  const resetLockout = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      await updateUser(id, { failed_login_count: 0 })
      reload()
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Could not reset the lockout counter.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />

      {justCreated && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
          User created.
        </div>
      )}

      {user && (
        <Card>
          <form onSubmit={submit} noValidate className="space-y-5">
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <TextField label="Full name" icon={UserIcon} value={form.full_name} onChange={set('full_name')} />
              <TextField label="Email" icon={MailIcon} type="email" value={form.email} onChange={set('email')} />
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <TextField label="Department" icon={BuildingIcon} value={form.department} onChange={set('department')} />
              <TextField label="Mobile" icon={PhoneIcon} value={form.mobile} onChange={set('mobile')} />
            </div>

            <TextField label="Address" icon={MapPinIcon} value={form.address} onChange={set('address')} />

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <TextField label="City" value={form.city} onChange={set('city')} />
              <TextField label="State" value={form.state} onChange={set('state')} />
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <SelectField label="Role" icon={ShieldIcon} value={form.role} onChange={set('role')}>
                {REGISTERABLE_ROLES.map((r) => (
                  <option key={r.value} value={r.value} className="bg-white text-slate-900">
                    {r.label}
                  </option>
                ))}
              </SelectField>

              <label className="flex items-center gap-2 self-end pb-2.5 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={set('is_active')}
                  className="h-4 w-4 rounded border-slate-300 bg-white accent-sky-500"
                />
                Account active
              </label>
            </div>

            {user.failed_login_count > 0 && (
              <div className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-700">
                <span>{user.failed_login_count} failed login attempt(s) on record.</span>
                <button
                  type="button"
                  onClick={resetLockout}
                  disabled={saving}
                  className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-400/20 disabled:opacity-50"
                >
                  Reset
                </button>
              </div>
            )}

            {saveError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                {saveError}
              </div>
            )}
            {saved && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
                User updated.
              </div>
            )}

            <button
              type="submit"
              disabled={saving}
              className="flex items-center justify-center gap-2 rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving && <SpinnerIcon className="h-4 w-4 animate-spin" />}
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </form>
        </Card>
      )}

      {loading && !user && <p className="text-sm text-slate-500">Loading user…</p>}
    </div>
  )
}
