import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { login } from '../api/client'

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const from = location.state?.from?.pathname || '/'

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const { data } = await login(username, password)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err?.response?.status === 401 ? 'Invalid credentials.' : 'Could not reach the backend.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0b0e14] px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-white/10 bg-white/[0.03] p-6">
        <div className="mb-6 flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-sky-400 to-emerald-400" />
          <div>
            <p className="text-sm font-semibold text-slate-100">IoMT IDS</p>
            <p className="text-[11px] text-slate-500">Attack Detection Console</p>
          </div>
        </div>

        <div className="space-y-3">
          <label className="block text-xs text-slate-400">
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-[#0d1017] px-3 py-2 text-sm text-slate-200 focus:border-sky-500/50 focus:outline-none"
              autoComplete="username"
            />
          </label>
          <label className="block text-xs text-slate-400">
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-white/10 bg-[#0d1017] px-3 py-2 text-sm text-slate-200 focus:border-sky-500/50 focus:outline-none"
              autoComplete="current-password"
            />
          </label>
        </div>

        {error && <p className="mt-3 text-xs text-amber-300">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded-lg bg-sky-500/15 py-2 text-sm font-medium text-sky-300 ring-1 ring-inset ring-sky-500/30 hover:bg-sky-500/25 disabled:opacity-50"
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
