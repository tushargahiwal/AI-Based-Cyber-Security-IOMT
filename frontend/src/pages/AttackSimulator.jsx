import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import {
  startSimulation,
  stopSimulation,
  getSimulationStatus,
  listDevices,
} from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import SelectField from '../components/SelectField'
import { MonitorIcon, SpinnerIcon, AlertTriangleIcon } from '../components/icons'

const MODES = [
  {
    value: 'mixed',
    label: 'Quiet traffic, then an attack',
    blurb:
      'Starts before the first attack in the capture so you can watch the verdicts turn over. Best for a demo.',
  },
  {
    value: 'attack',
    label: 'Attack traffic only',
    blurb: 'The longest unbroken attack run. Shows detection rate without benign traffic in the way.',
  },
  {
    value: 'benign',
    label: 'Benign traffic only',
    blurb: 'The longest clean run. Whatever gets flagged here is a false positive.',
  },
]

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

const POLL_MS = 1000

export default function AttackSimulator() {
  const { user } = useCurrentUser()
  const canRun = hasPermission(user, 'models.retrain')
  const { data: devices } = useApi(() => listDevices({ size: 100 }), [])

  const [form, setForm] = useState({ mode: 'mixed', rows: 120, speed: 4, device_id: '' })
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const timerRef = useRef(null)

  // Polls only while something is running — the status endpoint is cheap, but a
  // permanent 1 s poll on an idle page is log noise for no benefit. A failed
  // poll is swallowed on purpose: it must not wipe the last known state or spam
  // the banner, and the next button press will surface the real error.
  const poll = useCallback(async function tick() {
    try {
      const { data } = await getSimulationStatus()
      setState(data)
      if (data.status === 'running') {
        timerRef.current = setTimeout(tick, POLL_MS)
      }
    } catch {
      /* keep the last known state */
    }
  }, [])

  useEffect(() => {
    poll()
    return () => clearTimeout(timerRef.current)
  }, [poll])

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const start = async () => {
    setBusy(true)
    setError(null)
    try {
      const { data } = await startSimulation({
        mode: form.mode,
        rows: Number(form.rows),
        speed: Number(form.speed),
        device_id: form.device_id ? Number(form.device_id) : null,
      })
      setState(data)
      poll()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not start the simulation.'))
    } finally {
      setBusy(false)
    }
  }

  const stop = async () => {
    setBusy(true)
    try {
      const { data } = await stopSimulation()
      setState(data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not stop the simulation.'))
    } finally {
      setBusy(false)
    }
  }

  const running = state?.status === 'running'
  const progress = state?.total ? Math.round((state.processed / state.total) * 100) : 0
  const mode = MODES.find((m) => m.value === form.mode)

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />

      <Card title="Attack Simulator">
        <p className="text-sm text-slate-600">
          Replays real rows from the labelled WUSTL-EHMS-2020 capture through the live pipeline. The verdicts
          you see are genuine model output on genuine attack traffic — nothing here is scripted. Watch it land
          on the <Link to="/live" className="text-sky-600 hover:text-sky-800">Live Monitor</Link>.
        </p>

        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
          <SelectField label="What to replay" value={form.mode} onChange={set('mode')} disabled={running}>
            {MODES.map((m) => (
              <option key={m.value} value={m.value} className="bg-white text-slate-900">
                {m.label}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Target device"
            icon={MonitorIcon}
            value={form.device_id}
            onChange={set('device_id')}
            disabled={running}
          >
            <option value="" className="bg-white text-slate-500">
              First available life-critical device
            </option>
            {(devices?.items || []).map((d) => (
              <option key={d.id} value={d.id} className="bg-white text-slate-900">
                {d.device_uid}
              </option>
            ))}
          </SelectField>
        </div>
        <p className="mt-2 text-xs text-slate-500">{mode?.blurb}</p>

        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm text-slate-700">Rows: {form.rows}</span>
            <input
              type="range"
              min="10"
              max="500"
              step="10"
              value={form.rows}
              onChange={set('rows')}
              disabled={running}
              className="mt-2 w-full accent-sky-500"
            />
            <span className="mt-1 block text-xs text-slate-500">
              Stage 4 needs 31 readings before it can score, so keep this above ~40 to exercise all four stages.
            </span>
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Speed: {form.speed} rows/s</span>
            <input
              type="range"
              min="1"
              max="20"
              step="1"
              value={form.speed}
              onChange={set('speed')}
              disabled={running}
              className="mt-2 w-full accent-sky-500"
            />
            <span className="mt-1 block text-xs text-slate-500">
              About {Math.ceil(form.rows / Math.max(form.speed, 1))} s to run.
            </span>
          </label>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          {canRun ? (
            running ? (
              <button
                onClick={stop}
                disabled={busy}
                className="rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={start}
                disabled={busy}
                className="flex items-center gap-2 rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-sky-600 disabled:opacity-60"
              >
                {busy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                Start simulation
              </button>
            )
          ) : (
            <span className="flex items-center gap-2 text-sm text-slate-500">
              <AlertTriangleIcon className="h-4 w-4" />
              Running a simulation writes real detections and alerts, so it needs the model-retrain permission.
            </span>
          )}
        </div>
      </Card>

      {state && state.status !== 'idle' && (
        <Card title="Run status">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm capitalize text-slate-800">{state.status}</span>
            {state.device_uid && <span className="text-sm text-slate-600">on {state.device_uid}</span>}
            <span className="ml-auto text-sm tabular-nums text-slate-600">
              {state.processed} / {state.total}
            </span>
          </div>

          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-2 rounded-full transition-all ${state.status === 'failed' ? 'bg-red-400' : 'bg-sky-400'}`}
              style={{ width: `${progress}%` }}
            />
          </div>

          {state.error && <p className="mt-3 text-xs text-red-600">{state.error}</p>}

          <div className="mt-5 flex flex-wrap gap-2">
            {Object.entries(state.verdicts || {}).map(([verdict, count]) => (
              <span
                key={verdict}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs capitalize text-slate-700 ring-1 ring-inset ring-slate-200"
              >
                {verdict.replace(/_/g, ' ')}: <span className="tabular-nums text-slate-900">{count}</span>
              </span>
            ))}
            {state.alerts > 0 && (
              <span className="rounded-full bg-red-50 px-3 py-1 text-xs text-red-700 ring-1 ring-inset ring-red-200">
                alerts raised: <span className="tabular-nums">{state.alerts}</span>
              </span>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
