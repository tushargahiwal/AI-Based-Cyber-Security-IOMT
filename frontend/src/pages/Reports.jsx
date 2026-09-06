import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import {
  listReports,
  generateReport,
  deleteReport,
  downloadReport,
  listPatients,
  listDevices,
  listWards,
  REPORT_TYPES,
  ALERT_SEVERITIES,
  DETECTION_VERDICTS,
} from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import SelectField from '../components/SelectField'
import TextField from '../components/TextField'
import {
  SpinnerIcon,
  TrashIcon,
  DatabaseIcon,
  UserIcon,
  HistoryIcon,
  MonitorIcon,
  MapPinIcon,
} from '../components/icons'

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

// daily/weekly work out their own window; patient/device fall back to 30 days.
// The rest have no sensible default and the server rejects them without one.
const NEEDS_PERIOD = new Set(['incident', 'compliance', 'custom'])

/**
 * The sidebar's Reports sub-entries. Each one narrows the list AND presets the
 * generator, so "Patient reports" is a working section rather than a filtered
 * view someone still has to configure.
 */
const SCOPES = {
  patients: {
    heading: 'Patient reports',
    types: ['patient'],
    formType: 'patient',
    blurb: 'Everything one patient’s devices reported — alerts, detections and vitals.',
  },
  devices: {
    heading: 'Device reports',
    types: ['device'],
    formType: 'device',
    blurb: 'One device over a chosen window.',
  },
  wards: {
    heading: 'Ward reports',
    types: ['ward'],
    formType: 'ward',
    blurb: 'Every device in a ward, together.',
  },
  schedule: {
    heading: 'Daily & weekly reports',
    types: ['daily', 'weekly'],
    formType: 'daily',
    blurb: 'Routine estate-wide summaries over a fixed window.',
  },
}

const ALL_SCOPE = {
  heading: 'All reports',
  types: null,
  formType: 'patient',
  blurb: 'Every report, whoever generated it and whatever it covers.',
}

const TYPE_BLURB = {
  daily: 'The last 24 hours across the whole estate.',
  weekly: 'The last 7 days across the whole estate.',
  patient: "One patient: their devices, alerts, detections and vitals. Defaults to the last 30 days.",
  device: 'One device over the chosen window.',
  ward: 'Every device in one ward, over the chosen window.',
  incident: 'A specific window you choose — for writing up a single incident.',
  compliance: 'A specific window, for an audit or review.',
  custom: 'Any window, any combination of filters.',
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value}</p>
    </div>
  )
}

function Breakdown({ title, entries }) {
  const rows = Object.entries(entries || {})
  if (rows.length === 0) return null
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {rows.map(([k, v]) => (
          <span
            key={k}
            className="rounded-full bg-slate-100 px-3 py-1 text-xs capitalize text-slate-700 ring-1 ring-inset ring-slate-200"
          >
            {k.replace(/_/g, ' ')}: <span className="tabular-nums text-slate-900">{v}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function PatientScope({ patient }) {
  return (
    <div className="rounded-lg border border-sky-200 bg-sky-50 p-4">
      <p className="text-sm font-medium text-slate-900">Patient {patient.patient_code}</p>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
        {patient.age_band && <span>age {patient.age_band}</span>}
        {patient.sex && <span>sex {patient.sex}</span>}
        {patient.ward && <span>ward {patient.ward}</span>}
        <span>
          {patient.admitted_at ? `admitted ${new Date(patient.admitted_at).toLocaleDateString()}` : ''}
          {patient.discharged_at
            ? ` — discharged ${new Date(patient.discharged_at).toLocaleDateString()}`
            : patient.admitted_at
              ? ' — still admitted'
              : ''}
        </span>
      </div>
      {patient.devices?.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {patient.devices.map((d) => (
            <span
              key={d.id}
              className={`rounded-full px-2.5 py-0.5 text-xs ring-1 ring-inset ${
                d.life_critical
                  ? 'bg-red-50 text-red-700 ring-red-200'
                  : 'bg-slate-100 text-slate-700 ring-slate-200'
              }`}
              title={d.life_critical ? 'life-critical device' : d.type || ''}
            >
              {d.device_uid}
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-xs text-slate-500">
          No devices were assigned to this patient during the window.
        </p>
      )}
    </div>
  )
}

function ReportBody({ report }) {
  const s = report.summary_stats || {}
  const scope = s.scope || {}
  return (
    <div className="mt-4 space-y-5">
      {scope.patient && <PatientScope patient={scope.patient} />}
      {scope.device && (
        <p className="text-sm text-slate-700">
          Device <span className="font-mono">{scope.device.device_uid}</span> — {scope.device.type},
          ward {scope.device.ward || '—'}, status {scope.device.status}
        </p>
      )}
      {scope.ward && (
        <p className="text-sm text-slate-700">
          Ward {scope.ward.name} — {scope.ward.devices} devices, criticality {scope.ward.criticality}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric label="Detections" value={s.total_detections ?? 0} />
        <Metric label="Flagged share" value={`${((s.flagged_share ?? 0) * 100).toFixed(1)}%`} />
        <Metric label="Alerts" value={s.total_alerts ?? 0} />
        <Metric
          label="Avg latency"
          value={s.avg_inference_latency_ms != null ? `${s.avg_inference_latency_ms.toFixed(1)} ms` : '—'}
        />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Metric label="Vitals readings" value={s.vitals_readings ?? 0} />
        <Metric label="Scored by Stage 4" value={s.vitals_scored_by_stage4 ?? 0} />
        <Metric label="Implausible vitals" value={s.vitals_implausible ?? 0} />
      </div>

      <Breakdown title="Detections by verdict" entries={s.detections_by_verdict} />
      <Breakdown title="Alerts by severity" entries={s.alerts_by_severity} />
      <Breakdown title="Alerts by status" entries={s.alerts_by_status} />

      {s.top_attack_families?.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Attack families</p>
          <ul className="mt-2 space-y-1 text-sm text-slate-700">
            {s.top_attack_families.map((f) => (
              <li key={f.family}>
                {f.family} — <span className="tabular-nums text-slate-600">{f.alerts} alerts</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {s.busiest_devices?.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Busiest devices</p>
          <ul className="mt-2 space-y-1 text-sm text-slate-700">
            {s.busiest_devices.map((d) => (
              <li key={d.device_uid}>
                <span className="font-mono text-xs">{d.device_uid}</span> —{' '}
                <span className="tabular-nums text-slate-600">{d.detections} detections</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

const EMPTY_FORM = {
  report_type: 'patient',
  title: '',
  period_start: '',
  period_end: '',
  patient_id: '',
  device_id: '',
  ward: '',
  severity: '',
  verdict: '',
}

export default function Reports() {
  const { user } = useCurrentUser()
  const canGenerate = hasPermission(user, 'reports.generate')
  const { scope: scopeKey } = useParams()
  const scope = SCOPES[scopeKey] || ALL_SCOPE

  const [filters, setFilters] = useState({
    report_type: '',
    generated_by: '',
    patient_id: '',
    created_from: '',
    created_to: '',
  })
  const { data, loading, error, reload } = useApi(
    () =>
      listReports({
        size: 50,
        // A scope with one type filters server-side; 'schedule' covers two,
        // so those are narrowed client-side below.
        report_type: filters.report_type || (scope.types?.length === 1 ? scope.types[0] : undefined),
        generated_by: filters.generated_by ? Number(filters.generated_by) : undefined,
        patient_id: filters.patient_id ? Number(filters.patient_id) : undefined,
        created_from: filters.created_from ? new Date(filters.created_from).toISOString() : undefined,
        created_to: filters.created_to ? new Date(filters.created_to).toISOString() : undefined,
      }),
    [
      scopeKey,
      filters.report_type,
      filters.generated_by,
      filters.patient_id,
      filters.created_from,
      filters.created_to,
    ],
  )

  // Moving between sub-sections must not carry the previous one's filters or
  // leave the generator set to a type this section does not show.
  useEffect(() => {
    setFilters({ report_type: '', generated_by: '', patient_id: '', created_from: '', created_to: '' })
    setForm((f) => ({ ...EMPTY_FORM, report_type: scope.formType, title: '' }))
    setOpenId(null)
  }, [scopeKey])

  const visible = (data?.items || []).filter(
    (r) => !scope.types || scope.types.includes(r.report_type),
  )

  const { data: patients } = useApi(() => listPatients({ size: 200 }), [])
  const { data: devices } = useApi(() => listDevices({ size: 200 }), [])
  const { data: wards } = useApi(listWards, [])

  const [form, setForm] = useState({ ...EMPTY_FORM, report_type: scope.formType })
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState(null)
  const [openId, setOpenId] = useState(null)
  const [downloadingId, setDownloadingId] = useState(null)

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  const setFilter = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }))

  const needsPatient = form.report_type === 'patient'
  const needsDevice = form.report_type === 'device'
  const needsWard = form.report_type === 'ward'
  const needsPeriod = NEEDS_PERIOD.has(form.report_type)
  // The server rejects these too; disabling the button just avoids a round trip
  // to be told something the form already knows.
  const canSubmit =
    !busy &&
    !(needsPatient && !form.patient_id) &&
    !(needsDevice && !form.device_id) &&
    !(needsWard && !form.ward) &&
    !(needsPeriod && !form.period_start)

  const generate = async () => {
    setBusy(true)
    setFormError(null)
    try {
      await generateReport({
        report_type: form.report_type,
        title: form.title || null,
        period_start: form.period_start ? new Date(form.period_start).toISOString() : null,
        period_end: form.period_end ? new Date(form.period_end).toISOString() : null,
        patient_id: form.patient_id ? Number(form.patient_id) : null,
        device_id: form.device_id ? Number(form.device_id) : null,
        ward: form.ward || null,
        severity: form.severity || null,
        verdict: form.verdict || null,
      })
      setForm((f) => ({ ...f, title: '' }))
      reload()
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not generate the report.'))
    } finally {
      setBusy(false)
    }
  }

  const download = async (report) => {
    setDownloadingId(report.id)
    setFormError(null)
    try {
      await downloadReport(report.id)
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not download the report.'))
    } finally {
      setDownloadingId(null)
    }
  }

  const remove = async (id) => {
    try {
      await deleteReport(id)
      reload()
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not delete the report.'))
    }
  }

  const anyFilter = Object.values(filters).some(Boolean)

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />

      {canGenerate && (
        <Card title={`Generate a ${form.report_type} report`}>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <SelectField label="Type" icon={DatabaseIcon} value={form.report_type} onChange={set('report_type')}>
              {REPORT_TYPES.map((t) => (
                <option key={t} value={t} className="bg-white capitalize text-slate-900">
                  {t}
                </option>
              ))}
            </SelectField>
            <TextField
              label="Title (optional)"
              placeholder="Left blank, one is written from the subject and period"
              value={form.title}
              onChange={set('title')}
            />
          </div>
          <p className="mt-2 text-xs text-slate-500">{TYPE_BLURB[form.report_type]}</p>

          <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
            {needsPatient && (
              <SelectField label="Patient" icon={UserIcon} value={form.patient_id} onChange={set('patient_id')}>
                <option value="" className="bg-white text-slate-500">Choose a patient…</option>
                {(patients?.items || []).map((p) => (
                  <option key={p.id} value={p.id} className="bg-white text-slate-900">
                    {p.patient_code}
                    {p.ward ? ` — ${p.ward}` : ''}
                  </option>
                ))}
              </SelectField>
            )}
            {needsDevice && (
              <SelectField label="Device" icon={MonitorIcon} value={form.device_id} onChange={set('device_id')}>
                <option value="" className="bg-white text-slate-500">Choose a device…</option>
                {(devices?.items || []).map((d) => (
                  <option key={d.id} value={d.id} className="bg-white text-slate-900">
                    {d.device_uid}
                  </option>
                ))}
              </SelectField>
            )}
            {!needsPatient && !needsDevice && (
              <SelectField
                label={needsWard ? 'Ward' : 'Ward (optional)'}
                icon={MapPinIcon}
                value={form.ward}
                onChange={set('ward')}
              >
                <option value="" className="bg-white text-slate-500">
                  {needsWard ? 'Choose a ward…' : 'Whole estate'}
                </option>
                {(wards || []).map((w) => (
                  <option key={w.id} value={w.name} className="bg-white text-slate-900">
                    {w.name}
                  </option>
                ))}
              </SelectField>
            )}

            <div className="grid grid-cols-2 gap-4">
              <SelectField label="Severity" value={form.severity} onChange={set('severity')}>
                <option value="" className="bg-white text-slate-500">Any</option>
                {ALERT_SEVERITIES.map((s) => (
                  <option key={s} value={s} className="bg-white text-slate-900">{s}</option>
                ))}
              </SelectField>
              <SelectField label="Verdict" value={form.verdict} onChange={set('verdict')}>
                <option value="" className="bg-white text-slate-500">Any</option>
                {DETECTION_VERDICTS.map((v) => (
                  <option key={v} value={v} className="bg-white text-slate-900">
                    {v.replace(/_/g, ' ')}
                  </option>
                ))}
              </SelectField>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
            <TextField
              label={needsPeriod ? 'Period start (required)' : 'Period start (optional)'}
              type="datetime-local"
              value={form.period_start}
              onChange={set('period_start')}
            />
            <TextField
              label="Period end (optional)"
              type="datetime-local"
              value={form.period_end}
              onChange={set('period_end')}
            />
          </div>

          {formError && <p className="mt-3 text-sm text-red-700">{formError}</p>}

          <button
            onClick={generate}
            disabled={!canSubmit}
            className="mt-5 flex items-center gap-2 rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
            Generate
          </button>
          <p className="mt-3 text-xs text-slate-500">
            A report is a frozen snapshot of its window — reopening it shows what the system knew when it was
            generated, not what is true now.
          </p>
        </Card>
      )}

      <Card title={scope.heading}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <SelectField label="Type" value={filters.report_type} onChange={setFilter('report_type')}>
            <option value="" className="bg-white text-slate-500">All types</option>
            {(scope.types || REPORT_TYPES).map((t) => (
              <option key={t} value={t} className="bg-white capitalize text-slate-900">{t}</option>
            ))}
          </SelectField>

          <SelectField
            label="Generated by"
            icon={UserIcon}
            value={filters.generated_by}
            onChange={setFilter('generated_by')}
          >
            <option value="" className="bg-white text-slate-500">Everyone</option>
            {(data?.authors || []).map((a) => (
              <option key={a.id} value={a.id} className="bg-white text-slate-900">
                {a.username} ({a.reports})
              </option>
            ))}
          </SelectField>

          <SelectField label="Patient" value={filters.patient_id} onChange={setFilter('patient_id')}>
            <option value="" className="bg-white text-slate-500">Any patient</option>
            {(patients?.items || []).map((p) => (
              <option key={p.id} value={p.id} className="bg-white text-slate-900">
                {p.patient_code}
              </option>
            ))}
          </SelectField>

          <div className="grid grid-cols-2 gap-3">
            <TextField
              label="From"
              type="date"
              value={filters.created_from}
              onChange={setFilter('created_from')}
            />
            <TextField label="To" type="date" value={filters.created_to} onChange={setFilter('created_to')} />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          {anyFilter && (
            <button
              onClick={() =>
                setFilters({ report_type: '', generated_by: '', patient_id: '', created_from: '', created_to: '' })
              }
              className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-200"
            >
              Clear filters
            </button>
          )}
          <span className="ml-auto text-sm text-slate-600">
            {data ? `${visible.length} report${visible.length === 1 ? '' : 's'}` : ''}
          </span>
        </div>

        <p className="mt-3 text-xs text-slate-500">
          {scope.blurb} Everyone who can read reports sees every one of them, whoever generated it. The
          date filter is on when a report was generated, not the window it covers.
        </p>
      </Card>

      <Card>
        {loading && !data && <p className="text-sm text-slate-500">Loading…</p>}
        {data && visible.length === 0 && (
          <p className="text-sm text-slate-500">
            {anyFilter
              ? 'No reports match these filters.'
              : `No ${scope.heading.toLowerCase()} yet — generate one above.`}
          </p>
        )}

        <div className="space-y-3">
          {visible.map((r) => (
            <div key={r.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => setOpenId(openId === r.id ? null : r.id)}
                  className="text-left text-sm font-medium text-slate-900 hover:text-sky-800"
                >
                  {r.title || `${r.report_type} report #${r.id}`}
                </button>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs capitalize text-slate-600 ring-1 ring-inset ring-slate-200">
                  {r.report_type}
                </span>
                <span className="ml-auto text-xs text-slate-500">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : ''}
                </span>

                <button
                  onClick={() => download(r)}
                  disabled={downloadingId === r.id}
                  className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs text-slate-800 hover:bg-slate-200 disabled:opacity-50"
                  title="Download as Excel"
                >
                  {downloadingId === r.id ? (
                    <SpinnerIcon className="h-3 w-3 animate-spin" />
                  ) : (
                    <DatabaseIcon className="h-3 w-3" />
                  )}
                  Excel
                </button>

                {canGenerate && (
                  <button
                    onClick={() => remove(r.id)}
                    className="text-slate-500 hover:text-red-700"
                    title="Delete report"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                )}
              </div>

              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                <span className="flex items-center gap-1.5">
                  <HistoryIcon className="h-3.5 w-3.5" />
                  {r.period_start ? new Date(r.period_start).toLocaleString() : '?'} —{' '}
                  {r.period_end ? new Date(r.period_end).toLocaleString() : '?'}
                </span>
                <span className="flex items-center gap-1.5">
                  <UserIcon className="h-3.5 w-3.5" />
                  {r.generated_by_username || 'unknown user'}
                </span>
                {r.summary_stats?.scope?.patient && (
                  <span className="font-mono">{r.summary_stats.scope.patient.patient_code}</span>
                )}
                {r.summary_stats?.scope?.device && (
                  <span className="font-mono">{r.summary_stats.scope.device.device_uid}</span>
                )}
              </div>

              {openId === r.id && <ReportBody report={r} />}
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
