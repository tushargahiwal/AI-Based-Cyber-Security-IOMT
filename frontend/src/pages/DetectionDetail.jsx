import { useState } from 'react'
import { useParams } from 'react-router-dom'
import useApi from '../hooks/useApi'
import { getDetection, explainDetection } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'
import { ActivityIcon, AlertTriangleIcon, CheckCircleIcon, SpinnerIcon } from '../components/icons'

const VERDICT_STYLES = {
  benign: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  known_attack: 'bg-red-50 text-red-700 ring-red-200',
  uncertain: 'bg-amber-50 text-amber-700 ring-amber-200',
  zero_day_suspect: 'bg-orange-50 text-orange-700 ring-orange-200',
  data_integrity: 'bg-purple-50 text-purple-700 ring-purple-200',
}

// Flow features span wildly different magnitudes (a port number next to a
// duration in seconds), so pick a readable form per value rather than one format.
function formatValue(v) {
  if (Number.isInteger(v)) return String(v)
  if (Math.abs(v) >= 10000 || (v !== 0 && Math.abs(v) < 0.001)) return v.toExponential(2)
  return v.toFixed(4)
}

function Field({ label, value }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm text-slate-800">{value ?? '—'}</p>
    </div>
  )
}

export default function DetectionDetail() {
  const { id } = useParams()
  const { data: detection, loading, error } = useApi(() => getDetection(id), [id])
  const [explanation, setExplanation] = useState(null)
  const [explaining, setExplaining] = useState(false)
  const [explainError, setExplainError] = useState(null)

  // Bars are scaled against the largest contribution in this explanation, so
  // the ranking stays readable whether the top feature moved the score by 0.3
  // or by 0.005.
  const maxContribution = explanation
    ? Math.max(...explanation.top_features.map((f) => Math.abs(f.contribution)), Number.EPSILON)
    : 1

  const explain = async () => {
    setExplaining(true)
    setExplainError(null)
    try {
      const { data } = await explainDetection(id)
      setExplanation(data)
    } catch (err) {
      setExplainError(extractErrorMessage(err, 'Could not build an explanation.'))
    } finally {
      setExplaining(false)
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner error={error} />

      {detection && (
        <>
          <Card title="Verdict">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm capitalize ring-1 ring-inset ${VERDICT_STYLES[detection.final_verdict] || ''}`}
              >
                {detection.final_verdict.replace(/_/g, ' ')}
              </span>
              <span className="text-sm capitalize text-slate-600">severity: {detection.severity}</span>
              {detection.final_confidence != null && (
                <span className="ml-auto text-sm text-slate-600">
                  confidence: <span className="font-medium text-slate-800">{detection.final_confidence.toFixed(4)}</span>
                </span>
              )}
            </div>
          </Card>

          <Card title="Stage 1 — Binary Detector">
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
              <Field
                label="Label"
                value={
                  <span className="flex items-center gap-2">
                    <ActivityIcon className="h-3.5 w-3.5 text-slate-500" />
                    {detection.stage1_label}
                  </span>
                }
              />
              <Field label="Probability" value={detection.stage1_probability?.toFixed(5)} />
              <Field label="Inference latency" value={detection.inference_latency_ms != null ? `${detection.inference_latency_ms.toFixed(3)} ms` : null} />
            </div>
          </Card>

          {detection.stage2_attack_family ? (
            <Card title="Stage 2 — Attack Family Classifier">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
                <Field label="Attack family" value={detection.stage2_attack_family} />
                <Field label="Confidence" value={detection.stage2_confidence?.toFixed(5)} />
              </div>
            </Card>
          ) : (
            detection.stage1_label === 'malicious' && (
              <p className="text-xs text-slate-600">
                Stage 2 didn't confidently attribute a family for this flow (or predicted it as benign) — verdict
                fell back to <span className="text-slate-600">uncertain</span>.
              </p>
            )
          )}

          {detection.stage3_anomaly_score != null && (
            <Card title="Stage 3 — Zero-day / Autoencoder">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <Field
                  label="Anomaly"
                  value={
                    detection.stage3_is_anomaly ? (
                      <span className="flex items-center gap-2 text-orange-700">
                        <AlertTriangleIcon className="h-3.5 w-3.5" />
                        Flagged
                      </span>
                    ) : (
                      <span className="flex items-center gap-2 text-emerald-700">
                        <CheckCircleIcon className="h-3.5 w-3.5" />
                        Normal reconstruction
                      </span>
                    )
                  }
                />
                <Field label="Anomaly score" value={`${detection.stage3_anomaly_score.toFixed(3)} (threshold = 1.0)`} />
              </div>
              <p className="mt-3 text-xs text-slate-500">
                Runs on every flow, trained on benign traffic only — this is what catches attacks Stage 1/2 were
                never trained to recognise.
              </p>
            </Card>
          )}

          {detection.stage4_max_zscore != null && (
            <Card title="Stage 4 — Vitals Plausibility">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <Field
                  label="Reported vitals"
                  value={
                    detection.stage4_injection_suspected ? (
                      <span className="flex items-center gap-2 text-purple-700">
                        <AlertTriangleIcon className="h-3.5 w-3.5" />
                        Implausible — injection suspected
                      </span>
                    ) : (
                      <span className="flex items-center gap-2 text-emerald-700">
                        <CheckCircleIcon className="h-3.5 w-3.5" />
                        Consistent with recent history
                      </span>
                    )
                  }
                />
                <Field
                  label="Worst-vital deviation"
                  value={`${detection.stage4_max_zscore.toFixed(2)}σ from forecast (threshold = 3.00σ)`}
                />
              </div>
              <p className="mt-3 text-xs text-slate-500">
                An LSTM trained on benign vitals forecasts this device's next reading from its previous 30. A large
                deviation means the numbers the device reported don't follow from its own history — which is how a
                data-injection attack looks, but also how a genuinely deteriorating patient looks. At this threshold
                roughly 7% of benign windows are flagged, so treat it as corroboration, never as proof on its own.
              </p>
            </Card>
          )}

          <Card title="Context">
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
              <Field label="Detection ID" value={detection.id} />
              <Field label="Flow ID" value={detection.flow_id} />
              <Field label="Device ID" value={detection.device_id} />
              <Field label="Detected at" value={detection.detected_at ? new Date(detection.detected_at).toLocaleString() : null} />
            </div>
          </Card>

          {detection.stage4_max_zscore == null && (
            <p className="text-xs text-slate-600">
              Stage 4 didn't run for this detection — the device had no recent vitals reading scored against a full
              30-reading window.
            </p>
          )}

          <Card title="Why — SHAP attribution on Stage 1">
            {explanation ? (
              <>
                <p className="text-sm text-slate-700">{explanation.narrative}</p>
                <div className="mt-4 space-y-1.5">
                  {explanation.top_features.map((f) => {
                    const width = Math.min(100, (Math.abs(f.contribution) / maxContribution) * 100)
                    const up = f.contribution > 0
                    return (
                      <div key={f.feature} className="flex items-center gap-3 text-xs">
                        <span className="w-40 shrink-0 truncate font-mono text-slate-600" title={f.feature}>
                          {f.feature}
                        </span>
                        <span className="w-28 shrink-0 text-right font-mono text-slate-500">
                          {formatValue(f.value)}
                        </span>
                        <span className="flex h-2 flex-1 items-center">
                          <span
                            className={`h-2 rounded-sm ${up ? 'bg-red-500' : 'bg-emerald-500'}`}
                            style={{ width: `${width}%` }}
                          />
                        </span>
                        <span
                          className={`w-20 shrink-0 text-right font-mono ${up ? 'text-red-700' : 'text-emerald-700'}`}
                        >
                          {f.contribution > 0 ? '+' : ''}
                          {f.contribution.toFixed(4)}
                        </span>
                      </div>
                    )
                  })}
                </div>
                <p className="mt-4 text-xs text-slate-500">
                  Red pushed the score toward malicious, green toward benign, relative to an average flow
                  ({explanation.base_value?.toFixed(3)}). Only the {explanation.top_features.length} largest of
                  44 features are shown, so they don't sum to the full gap.
                </p>
              </>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={explain}
                  disabled={explaining}
                  className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-200 disabled:opacity-50"
                >
                  {explaining && <SpinnerIcon className="h-3.5 w-3.5 animate-spin" />}
                  {explaining ? 'Computing…' : 'Explain this verdict'}
                </button>
                <span className="text-xs text-slate-500">
                  Ranks the 44 flow features by how much each moved the Stage 1 score.
                </span>
              </div>
            )}
            {explainError && <p className="mt-3 text-xs text-red-600">{explainError}</p>}
          </Card>
        </>
      )}

      {loading && !detection && <p className="text-sm text-slate-500">Loading detection…</p>}
    </div>
  )
}
