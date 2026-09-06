import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { register, REGISTERABLE_ROLES } from '../api/client'
import { extractErrorMessage, errorStatus } from '../api/errors'
import Card from '../components/Card'
import TextField from '../components/TextField'
import SelectField from '../components/SelectField'
import PasswordField from '../components/PasswordField'
import PasswordStrength, { scorePassword } from '../components/PasswordStrength'
import { UserIcon, MailIcon, BuildingIcon, PhoneIcon, MapPinIcon, ShieldIcon, SpinnerIcon } from '../components/icons'

const DEPARTMENT_SUGGESTIONS = ['IT Security', 'ICU', 'Biomedical Engineering', 'Network Operations', 'Administration']

const USERNAME_PATTERN = /^[a-zA-Z0-9_.-]{3,64}$/
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const MOBILE_PATTERN = /^\+?[0-9\-\s]{7,15}$/

const initialForm = {
  full_name: '',
  username: '',
  email: '',
  department: '',
  mobile: '',
  address: '',
  city: '',
  state: '',
  role: 'viewer',
  password: '',
  confirm_password: '',
}

export default function CreateUser() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const validate = () => {
    const next = {}
    if (!form.full_name.trim()) next.full_name = 'Full name is required.'

    if (!form.username.trim()) next.username = 'Username is required.'
    else if (!USERNAME_PATTERN.test(form.username.trim()))
      next.username = '3–64 characters: letters, numbers, dot, dash or underscore.'

    if (!form.email.trim()) next.email = 'Email is required.'
    else if (!EMAIL_PATTERN.test(form.email.trim())) next.email = 'Enter a valid email address.'

    if (!form.password) next.password = 'Password is required.'
    else if (form.password.length < 8) next.password = 'Use at least 8 characters.'
    else if (form.password.length > 72) next.password = 'Use 72 characters or fewer.'
    else if (scorePassword(form.password) < 2) next.password = 'Add more variety — mix case, numbers or symbols.'

    if (form.confirm_password !== form.password) next.confirm_password = 'Passwords do not match.'

    if (form.mobile.trim() && !MOBILE_PATTERN.test(form.mobile.trim()))
      next.mobile = 'Enter a valid mobile number.'

    setErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async (e) => {
    e.preventDefault()
    setFormError(null)
    if (!validate()) return

    setBusy(true)
    try {
      const { data } = await register({
        full_name: form.full_name.trim(),
        username: form.username.trim(),
        email: form.email.trim(),
        department: form.department.trim() || undefined,
        mobile: form.mobile.trim() || undefined,
        address: form.address.trim() || undefined,
        city: form.city.trim() || undefined,
        state: form.state.trim() || undefined,
        role: form.role,
        password: form.password,
      })
      navigate(`/users/${data.id}`, { state: { justCreated: true } })
    } catch (err) {
      if (errorStatus(err) === 409) {
        setFormError('That username or email is already registered.')
      } else {
        setFormError(extractErrorMessage(err, 'Could not create this user.'))
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
              label="Full name"
              icon={UserIcon}
              placeholder="Rohit Patil"
              autoComplete="name"
              autoFocus
              value={form.full_name}
              onChange={set('full_name')}
              error={errors.full_name}
            />
            <TextField
              label="Username"
              icon={UserIcon}
              placeholder="analyst_rohit"
              autoComplete="username"
              value={form.username}
              onChange={set('username')}
              error={errors.username}
            />
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label="Email"
              icon={MailIcon}
              type="email"
              placeholder="you@hospital.org"
              autoComplete="email"
              value={form.email}
              onChange={set('email')}
              error={errors.email}
            />
            <TextField
              label="Department"
              icon={BuildingIcon}
              list="department-suggestions"
              placeholder="IT Security"
              autoComplete="organization-title"
              value={form.department}
              onChange={set('department')}
            />
          </div>
          <datalist id="department-suggestions">
            {DEPARTMENT_SUGGESTIONS.map((d) => (
              <option key={d} value={d} />
            ))}
          </datalist>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label="Mobile"
              icon={PhoneIcon}
              type="tel"
              placeholder="+91 98765 43210"
              autoComplete="tel"
              value={form.mobile}
              onChange={set('mobile')}
              error={errors.mobile}
            />
            <TextField
              label="Address"
              icon={MapPinIcon}
              placeholder="Street address"
              autoComplete="street-address"
              value={form.address}
              onChange={set('address')}
            />
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label="City"
              icon={MapPinIcon}
              placeholder="Nashik"
              autoComplete="address-level2"
              value={form.city}
              onChange={set('city')}
            />
            <TextField
              label="State"
              icon={MapPinIcon}
              placeholder="Maharashtra"
              autoComplete="address-level1"
              value={form.state}
              onChange={set('state')}
            />
          </div>

          <SelectField label="Role" icon={ShieldIcon} value={form.role} onChange={set('role')}>
            {REGISTERABLE_ROLES.map((r) => (
              <option key={r.value} value={r.value} className="bg-white text-slate-900">
                {r.label}
              </option>
            ))}
          </SelectField>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <div>
              <PasswordField
                label="Password"
                placeholder="At least 8 characters"
                autoComplete="new-password"
                value={form.password}
                onChange={set('password')}
                error={errors.password}
              />
              <PasswordStrength password={form.password} />
            </div>
            <PasswordField
              label="Confirm password"
              placeholder="Re-enter password"
              autoComplete="new-password"
              value={form.confirm_password}
              onChange={set('confirm_password')}
              error={errors.confirm_password}
            />
          </div>

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
            {busy ? 'Creating…' : 'Create user'}
          </button>
        </form>
      </Card>
    </div>
  )
}
