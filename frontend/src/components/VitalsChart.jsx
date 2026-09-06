import { useMemo, useState } from 'react'
import { VITAL_FIELDS } from '../api/client'

const WIDTH = 720
const HEIGHT = 220
const PAD = { top: 12, right: 12, bottom: 24, left: 44 }

/**
 * Reported vitals against what the Stage 4 forecaster expected.
 *
 * This is the one view where a data-injection attack is obvious to a human: the
 * forecast line keeps following the patient's own trend while the reported line
 * jumps away from it. Drawn as inline SVG rather than pulling in a chart
 * library — two series and a threshold band do not justify the dependency.
 */
export default function VitalsChart({ readings }) {
  const [vital, setVital] = useState(VITAL_FIELDS[0])

  // The API returns newest first; a chart reads left to right in time order.
  const series = useMemo(() => {
    return [...readings]
      .reverse()
      .map((r) => ({
        at: new Date(r.recorded_at),
        actual: r[vital.key] == null ? null : Number(r[vital.key]),
        predicted: r.predicted_values?.predicted?.[vital.modelKey] ?? null,
        flagged: r.injection_suspected,
        z: r.residual_zscore,
      }))
      .filter((p) => p.actual != null)
  }, [readings, vital])

  const scored = series.filter((p) => p.predicted != null)

  if (series.length < 2) {
    return (
      <p className="text-sm text-slate-500">
        Not enough readings to plot yet.
      </p>
    )
  }

  const values = series.flatMap((p) => [p.actual, p.predicted]).filter((v) => v != null)
  let min = Math.min(...values)
  let max = Math.max(...values)
  // A flat series would collapse to a zero-height plot; give it some room.
  if (max - min < 1e-6) {
    min -= 1
    max += 1
  }
  const span = max - min
  min -= span * 0.1
  max += span * 0.1

  const plotW = WIDTH - PAD.left - PAD.right
  const plotH = HEIGHT - PAD.top - PAD.bottom
  const x = (i) => PAD.left + (i / (series.length - 1)) * plotW
  const y = (v) => PAD.top + plotH - ((v - min) / (max - min)) * plotH

  const path = (key) =>
    series
      .map((p, i) => (p[key] == null ? null : `${x(i)},${y(p[key])}`))
      .reduce((acc, point) => {
        if (point == null) return { d: acc.d, pen: 'M' }
        return { d: `${acc.d}${acc.pen}${point} `, pen: 'L' }
      }, { d: '', pen: 'M' }).d

  const ticks = [min, (min + max) / 2, max]

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {VITAL_FIELDS.map((f) => (
          <button
            key={f.key}
            onClick={() => setVital(f)}
            className={`rounded-full px-2.5 py-1 text-xs ring-1 ring-inset transition-colors ${
              f.key === vital.key
                ? 'bg-sky-100 text-sky-700 ring-sky-300'
                : 'bg-slate-100 text-slate-600 ring-slate-200 hover:bg-slate-200'
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto flex items-center gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 bg-sky-400" /> reported
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 border-t border-dashed border-slate-300" /> forecast
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-purple-400" /> implausible
          </span>
        </span>
      </div>

      <div className="mt-3 overflow-x-auto">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full min-w-[36rem]" role="img"
             aria-label={`${vital.label} reported against the Stage 4 forecast`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(t)} y2={y(t)}
                    stroke="currentColor" className="text-slate-200" />
              <text x={PAD.left - 8} y={y(t) + 4} textAnchor="end"
                    className="fill-slate-500 text-[10px]">
                {t.toFixed(t > 50 ? 0 : 1)}
              </text>
            </g>
          ))}

          {scored.length > 0 && (
            <path d={path('predicted')} fill="none" stroke="currentColor" strokeWidth="1.5"
                  strokeDasharray="4 3" className="text-slate-500" />
          )}
          <path d={path('actual')} fill="none" stroke="currentColor" strokeWidth="2"
                className="text-sky-600" />

          {series.map((p, i) =>
            p.flagged ? (
              <circle key={i} cx={x(i)} cy={y(p.actual)} r="4"
                      className="fill-purple-400"
                      stroke="currentColor" strokeWidth="1" strokeOpacity="0.3">
                <title>
                  {`${vital.label} ${p.actual}${vital.unit} — ${Number(p.z).toFixed(2)}σ off forecast`}
                </title>
              </circle>
            ) : null,
          )}

          <text x={PAD.left} y={HEIGHT - 6} className="fill-slate-400 text-[10px]">
            {series[0].at.toLocaleTimeString()}
          </text>
          <text x={WIDTH - PAD.right} y={HEIGHT - 6} textAnchor="end"
                className="fill-slate-400 text-[10px]">
            {series[series.length - 1].at.toLocaleTimeString()}
          </text>
        </svg>
      </div>

      <p className="mt-2 text-xs text-slate-500">
        {scored.length === 0
          ? 'No forecast yet — Stage 4 needs 31 consecutive readings from this device before it can predict.'
          : `${scored.length} of ${series.length} readings scored by Stage 4. Where the two lines separate, the device reported something its own recent history does not lead to.`}
      </p>
    </div>
  )
}
