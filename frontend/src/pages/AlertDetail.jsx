import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import useApi from '../hooks/useApi'
import useCurrentUser from '../hooks/useCurrentUser'
import {
  getAlert,
  acknowledgeAlert,
  assignAlert,
  resolveAlert,
  markAlertFalsePositive,
  commentOnAlert,
  applyRecommendation,
  revertRecommendation,
  ENFORCING_ACTIONS,
} from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import TextField from '../components/TextField'
import { BellIcon, MessageIcon, UserCheckIcon, CheckCircleIcon, SpinnerIcon } from '../components/icons'

const STATUS_STYLES = {
  new: 'bg-red-50 text-red-700 ring-red-200',
  acknowledged: 'bg-amber-50 text-amber-700 ring-amber-200',
  investigating: 'bg-sky-50 text-sky-700 ring-sky-200',
  resolved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  false_positive: 'bg-slate-100 text-slate-600 ring-slate-200',
}

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

function Field({ label, value }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-slate-800">{value ?? '—'}</p>
    </div>
  )
}

function ApplyButton({ rec, busy, canQuarantine, onApply }) {
  const [confirming, setConfirming] = useState(false)
  const enforcing = ENFORCING_ACTIONS.includes(rec.action_type)

  // The server refuses an enforcing action on a life-critical device unless the
  // caller confirms. is_automatable is cleared for exactly those devices when the
  // recommendation is generated, so it's the signal to ask first.
  const needsConfirm = enforcing && !rec.is_automatable

  if (enforcing && !canQuarantine) {
    return <span className="text-xs text-slate-500">Needs the device-quarantine permission to apply.</span>
  }

  if (confirming) {
    return (
      <>
        <span className="text-xs text-amber-700">
          This can interrupt patient care on a life-critical device. Apply anyway?
        </span>
        <button
          onClick={() => { setConfirming(false); onApply(true) }}
          disabled={busy}
          className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50"
        >
          Yes, apply
        </button>
        <button
          onClick={() => setConfirming(false)}
          disabled={busy}
          className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-200 disabled:opacity-50"
        >
          Cancel
        </button>
      </>
    )
  }

  return (
    <button
      onClick={() => (needsConfirm ? setConfirming(true) : onApply(false))}
      disabled={busy}
      className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs text-slate-800 hover:bg-slate-200 disabled:opacity-50"
    >
      {busy && <SpinnerIcon className="h-3 w-3 animate-spin" />}
      {enforcing ? 'Apply' : 'Mark as done'}
    </button>
  )
}

export default function AlertDetail() {
  const { id } = useParams()
  const { user } = useCurrentUser()
  const { data: alert, loading, error, reload } = useApi(() => getAlert(id), [id])

  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [notes, setNotes] = useState('')
  const [comment, setComment] = useState('')
  const [appliedEffect, setAppliedEffect] = useState(null)

  const canAck = hasPermission(user, 'alerts.ack')
  const canAssign = hasPermission(user, 'alerts.assign')
  const canResolve = hasPermission(user, 'alerts.resolve')
  const canComment = hasPermission(user, 'alerts.comment')
  // The backend enforces this too; mirroring it here just avoids offering a
  // button that would come back 403.
  const canQuarantine = hasPermission(user, 'devices.quarantine')

  const isOpen = alert && !['resolved', 'false_positive'].includes(alert.status)

  const run = async (fn) => {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
      reload()
    } catch (err) {
      setActionError(extractErrorMessage(err, 'Action failed.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />
      {actionError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
          {actionError}
        </div>
      )}

      {alert && (
        <>
          <Card title="Status">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm capitalize ring-1 ring-inset ${STATUS_STYLES[alert.status] || ''}`}
              >
                <BellIcon className="h-3.5 w-3.5" />
                {alert.status.replace(/_/g, ' ')}
              </span>
              <span className="text-sm capitalize text-slate-600">severity: {alert.severity}</span>
              <span className="text-sm text-slate-600">
                risk score: <span className="font-mono font-semibold text-slate-800">{alert.risk_score?.toFixed(0)}</span>
              </span>
              {alert.occurrence_count > 1 && (
                <span className="text-sm text-slate-600">×{alert.occurrence_count} occurrences</span>
              )}
              {alert.assignee_username && (
                <span className="ml-auto flex items-center gap-1.5 text-sm text-slate-600">
                  <UserCheckIcon className="h-3.5 w-3.5" />
                  {alert.assignee_username}
                </span>
              )}
            </div>

            {isOpen && (
              <div className="mt-4 flex flex-wrap gap-2">
                {canAck && alert.status === 'new' && (
                  <button
                    onClick={() => run(() => acknowledgeAlert(id))}
                    disabled={busy}
                    className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200 disabled:opacity-50"
                  >
                    Acknowledge
                  </button>
                )}
                {canAssign && alert.assigned_to !== user?.id && (
                  <button
                    onClick={() => run(() => assignAlert(id, user.id))}
                    disabled={busy}
                    className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200 disabled:opacity-50"
                  >
                    <UserCheckIcon className="h-4 w-4" />
                    Assign to me
                  </button>
                )}
              </div>
            )}
          </Card>

          <Card title="Details">
            <p className="text-sm text-slate-700">{alert.description}</p>
            <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-3">
              <Field label="Alert" value={alert.alert_uid} />
              <Field
                label="Device"
                value={alert.device_uid ? <Link to={`/devices/${alert.device_id}`} className="text-sky-600 hover:text-sky-800">{alert.device_uid}</Link> : null}
              />
              <Field
                label="Patient"
                value={alert.patient_code ? <Link to={`/patients/${alert.patient_id}`} className="text-sky-600 hover:text-sky-800">{alert.patient_code}</Link> : null}
              />
              <Field label="Attack family" value={alert.attack_family} />
              <Field label="First seen" value={alert.first_seen_at ? new Date(alert.first_seen_at).toLocaleString() : null} />
              <Field label="Last seen" value={alert.last_seen_at ? new Date(alert.last_seen_at).toLocaleString() : null} />
            </div>
          </Card>

          {alert.recommendations.length > 0 && (
            <Card title="Recommended actions">
              <div className="space-y-3">
                {alert.recommendations.map((rec) => (
                  <div key={rec.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 ring-1 ring-inset ring-slate-200">
                        {rec.action_type?.replace(/_/g, ' ') || 'manual review'}
                      </span>
                      {rec.is_automatable ? (
                        <span className="text-xs text-amber-700">automatable (needs approval)</span>
                      ) : (
                        <span className="text-xs text-slate-500">manual only</span>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-slate-700">{rec.recommendation}</p>
                    {rec.target && <p className="mt-1 font-mono text-xs text-slate-500">target: {rec.target}</p>}

                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      {rec.applied ? (
                        <>
                          <span className="flex items-center gap-1.5 text-xs text-emerald-700">
                            <CheckCircleIcon className="h-3.5 w-3.5" />
                            Applied {rec.applied_at ? new Date(rec.applied_at).toLocaleString() : ''}
                          </span>
                          {/* Putting a device back is the safe direction, so it is
                              always one click — no confirmation stands in the way. */}
                          <button
                            onClick={() =>
                              run(async () => {
                                const { data } = await revertRecommendation(id, rec.id)
                                setAppliedEffect(`Undone — ${data.effect}`)
                              })
                            }
                            disabled={busy}
                            className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                          >
                            Undo
                          </button>
                        </>
                      ) : (
                        isOpen &&
                        canAck && (
                          <ApplyButton
                            rec={rec}
                            busy={busy}
                            canQuarantine={canQuarantine}
                            onApply={(confirm) =>
                              run(async () => {
                                const { data } = await applyRecommendation(id, rec.id, confirm)
                                setAppliedEffect(data.effect)
                              })
                            }
                          />
                        )
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {appliedEffect && (
                <p className="mt-3 text-xs text-emerald-700">Applied — {appliedEffect}</p>
              )}
              <p className="mt-3 text-xs text-slate-500">
                Nothing here runs on its own. Applying one records who took it on, and for
                isolate/block/revoke also carries it out — a quarantine lifts itself after 4 hours and a
                block after 24, so a device cut off during a night shift is never left that way.
              </p>
            </Card>
          )}

          {isOpen && (canResolve || canComment) && (
            <Card title="Resolve / Comment">
              <div className="space-y-4">
                <TextField
                  label="Notes / comment"
                  placeholder="What did you find or do?"
                  value={notes}
                  onChange={(e) => { setNotes(e.target.value); setComment(e.target.value) }}
                />
                <div className="flex flex-wrap gap-2">
                  {canComment && (
                    <button
                      onClick={() => run(async () => { await commentOnAlert(id, comment); setComment(''); setNotes('') })}
                      disabled={busy || !comment.trim()}
                      className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200 disabled:opacity-50"
                    >
                      <MessageIcon className="h-4 w-4" />
                      Add comment
                    </button>
                  )}
                  {canResolve && (
                    <>
                      <button
                        onClick={() => run(async () => { await resolveAlert(id, notes || undefined); setNotes(''); setComment('') })}
                        disabled={busy}
                        className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
                      >
                        {busy && <SpinnerIcon className="h-4 w-4 animate-spin" />}
                        <CheckCircleIcon className="h-4 w-4" />
                        Resolve
                      </button>
                      <button
                        onClick={() => run(async () => { await markAlertFalsePositive(id, notes || undefined); setNotes(''); setComment('') })}
                        disabled={busy}
                        className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                      >
                        Mark false positive
                      </button>
                    </>
                  )}
                </div>
              </div>
            </Card>
          )}

          {alert.resolution_notes && (
            <Card title="Resolution">
              <p className="text-sm text-slate-700">{alert.resolution_notes}</p>
            </Card>
          )}

          <Card title="Action history">
            <div className="space-y-3">
              {alert.actions.map((act) => (
                <div key={act.id} className="flex items-start gap-3 text-sm">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300" />
                  <div>
                    <p className="text-slate-700">
                      <span className="font-medium text-slate-800">{act.username || 'System'}</span>{' '}
                      {act.action.replace(/_/g, ' ')}
                      {act.previous_status && act.new_status && act.previous_status !== act.new_status && (
                        <span className="text-slate-500"> ({act.previous_status} → {act.new_status})</span>
                      )}
                    </p>
                    {act.comment && <p className="mt-0.5 text-slate-600">{act.comment}</p>}
                    <p className="mt-0.5 text-xs text-slate-600">
                      {act.created_at ? new Date(act.created_at).toLocaleString() : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Link to={`/detections/${alert.detection_id}`} className="inline-block text-sm text-sky-600 hover:text-sky-800">
            View underlying detection →
          </Link>
        </>
      )}

      {loading && !alert && <p className="text-sm text-slate-500">Loading alert…</p>}
    </div>
  )
}
