import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { login } from '../api/client'
import { saveTokens } from '../api/tokens'
import { extractErrorMessage } from '../api/errors'
import AuthLayout from '../components/AuthLayout'
import TextField from '../components/TextField'
import PasswordField from '../components/PasswordField'
import { UserIcon, SpinnerIcon } from '../components/icons'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/'

  const [form, setForm] = useState({ username: '', password: '' })
  const [remember, setRemember] = useState(true)
  const [showRecovery, setShowRecovery] = useState(false)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [busy, setBusy] = useState(false)
  const justRegistered = location.state?.justRegistered

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const validate = () => {
    const next = {}
    if (!form.username.trim()) next.username = 'Username is required.'
    if (!form.password) next.password = 'Password is required.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async (e) => {
    e.preventDefault()
    setFormError(null)
    if (!validate()) return

    setBusy(true)
    try {
      const { data } = await login(form.username.trim(), form.password)
      saveTokens({
        access: data.access_token,
        refresh: data.refresh_token,
        persistent: remember,
      })
      navigate(from, { replace: true })
    } catch (err) {
      const message =
        err?.response?.status === 401
          ? 'Incorrect username or password.'
          : extractErrorMessage(err, 'Sign-in failed. Please try again.')
      setFormError(message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      showBranding={false}
      showLogo={false}
      eyebrow="Welcome back"
      footer={
        <>
          Don&apos;t have an account?{' '}
          <Link to="/register" className="font-medium text-sky-600 hover:text-sky-800">
           Register Now
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        {justRegistered && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
            Account created — sign in with your new credentials.
          </div>
        )}

        <TextField
          label="Username"
          icon={UserIcon}
          placeholder="e.g. analyst_rohit"
          autoComplete="username"
          autoFocus
          value={form.username}
          onChange={set('username')}
          error={errors.username}
        />

        <PasswordField
          label="Password"
          placeholder="••••••••"
          autoComplete="current-password"
          value={form.password}
          onChange={set('password')}
          error={errors.password}
        />

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 bg-white accent-sky-500"
            />
            Keep me signed in
          </label>
          <button
            type="button"
            onClick={() => setShowRecovery((v) => !v)}
            className="text-sm text-slate-600 underline-offset-2 hover:text-slate-800 hover:underline"
          >
            Forgot password?
          </button>
        </div>

        {showRecovery && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-3 text-sm text-slate-600">
            There is no self-service reset: accounts here map to hospital staff, so a password is
            reset by an administrator who can confirm who you are. Ask your IT Security admin to
            reset it from <span className="text-slate-700">Users</span>.
          </div>
        )}

        {formError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
            {formError}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-sky-500 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthLayout>
  )
}
