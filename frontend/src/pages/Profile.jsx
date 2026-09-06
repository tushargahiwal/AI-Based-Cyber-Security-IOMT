import { useEffect, useState } from 'react'
import { updateUser } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import useCurrentUser from '../hooks/useCurrentUser'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import TextField from '../components/TextField'
import { UserIcon, MailIcon, BuildingIcon, PhoneIcon, MapPinIcon, SpinnerIcon } from '../components/icons'

const EMPTY_FORM = {
  full_name: '',
  email: '',
  department: '',
  mobile: '',
  address: '',
  city: '',
  state: '',
}

export default function Profile() {
  const { user, loading, error, reload } = useCurrentUser()
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
    })
  }, [user])

  const set = (key) => (e) => {
    setSaved(false)
    setForm((f) => ({ ...f, [key]: e.target.value }))
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!user) return
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      await updateUser(user.id, form)
      setSaved(true)
      reload()
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Could not update your profile.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />

      {user && (
        <Card>
          <div className="mb-5 flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium text-slate-800">{user.username}</span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs capitalize text-slate-600 ring-1 ring-inset ring-slate-200">
              {user.role}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs ring-1 ring-inset ${
                user.is_active
                  ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                  : 'bg-red-50 text-red-700 ring-red-200'
              }`}
            >
              {user.is_active ? 'Active' : 'Deactivated'}
            </span>
          </div>

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

            {saveError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                {saveError}
              </div>
            )}
            {saved && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
                Profile updated.
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

      {loading && !user && <p className="text-sm text-slate-500">Loading your profile…</p>}
    </div>
  )
}
