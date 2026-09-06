import useApi from '../hooks/useApi'
import { getModelEvaluation } from '../api/client'
import Card from './Card'

function pct(value) {
  return value == null ? '—' : `${(value * 100).toFixed(2)}%`
}

function Metric({ label, value, tone = 'text-slate-900' }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  )
}

/**
 * A 2x2 confusion matrix laid out the way it is read: predicted across the top,
 * actual down the side. The two error cells are coloured because they are the
 * ones that matter operationally — a false negative is an attack that got
 * through, a false positive is an analyst's wasted afternoon.
 */
function ConfusionMatrix({ matrix }) {
  if (!matrix || matrix.length !== 2) return null
  const [[tn, fp], [fn, tp]] = matrix
  const total = tn + fp + fn + tp

  const Cell = ({ value, label, tone }) => (
    <td className={`border border-slate-200 px-4 py-3 text-center ${tone}`}>
      <span className="block text-lg font-semibold tabular-nums">{value}</span>
      <span className="block text-[10px] uppercase tracking-wide opacity-70">{label}</span>
    </td>
  )

  return (
    <div className="overflow-x-auto">
      <table className="text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2" />
            <th className="px-3 py-2 font-medium" colSpan={2}>
              Predicted
            </th>
          </tr>
          <tr className="text-xs text-slate-500">
            <th className="px-3 py-1 text-left font-medium">Actual</th>
            <th className="px-3 py-1 font-normal">benign</th>
            <th className="px-3 py-1 font-normal">malicious</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th className="px-3 py-2 text-left text-xs font-normal text-slate-500">benign</th>
            <Cell value={tn} label="correct" tone="text-emerald-700" />
            <Cell value={fp} label="false alarm" tone="text-amber-700" />
          </tr>
          <tr>
            <th className="px-3 py-2 text-left text-xs font-normal text-slate-500">malicious</th>
            <Cell value={fn} label="missed" tone="text-red-700" />
            <Cell value={tp} label="caught" tone="text-emerald-700" />
          </tr>
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">
        {total} flows in the test split. {fn} attack{fn === 1 ? '' : 's'} got through; {fp} benign
        flow{fp === 1 ? '' : 's'} raised a false alarm.
      </p>
    </div>
  )
}

function FeatureImportances({ importances }) {
  if (!importances?.length) return null
  const max = Math.max(...importances.map((f) => f.importance_gain || 0), Number.EPSILON)
  return (
    <div className="space-y-1.5">
      {importances.map((f) => (
        <div key={f.feature_name} className="flex items-center gap-3 text-xs">
          <span className="w-6 shrink-0 text-right tabular-nums text-slate-600">{f.rank}</span>
          <span className="w-44 shrink-0 truncate font-mono text-slate-600" title={f.feature_name}>
            {f.feature_name}
          </span>
          <span className="flex h-2 flex-1 items-center">
            <span
              className="h-2 rounded-sm bg-sky-500"
              style={{ width: `${((f.importance_gain || 0) / max) * 100}%` }}
            />
          </span>
          <span className="w-20 shrink-0 text-right font-mono tabular-nums text-slate-500">
            {(f.importance_gain ?? 0).toFixed(4)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function ModelEvaluation({ modelId }) {
  const { data, loading } = useApi(() => getModelEvaluation(modelId), [modelId])

  if (loading && !data) return null
  const run = data?.training_runs?.[0]
  const metric = run?.metrics?.find((m) => m.split === 'test') || run?.metrics?.[0]

  if (!run || !metric) {
    return (
      <Card title="Measured results">
        <p className="text-sm text-slate-500">
          No evaluation recorded for this model. Train it with a script in{' '}
          <span className="font-mono text-slate-600">ml/</span>, then run{' '}
          <span className="font-mono text-slate-600">backend/register_models.py</span> to load the
          numbers in.
        </p>
      </Card>
    )
  }

  return (
    <>
      <Card title="Measured results">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Metric label="Accuracy" value={pct(metric.accuracy)} />
          <Metric label="Precision" value={pct(metric.precision)} />
          <Metric
            label="Recall"
            value={pct(metric.recall)}
            tone={metric.recall != null && metric.recall < 0.8 ? 'text-amber-700' : 'text-slate-900'}
          />
          <Metric label="F1" value={pct(metric.f1_score)} />
          <Metric label="ROC-AUC" value={metric.roc_auc?.toFixed(4) ?? '—'} />
          <Metric
            label="False positives"
            value={pct(metric.false_positive_rate)}
            tone={
              metric.false_positive_rate != null && metric.false_positive_rate > 0.05
                ? 'text-amber-700'
                : 'text-slate-900'
            }
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
          <span>split: {metric.split}</span>
          {run.dataset_name && <span>dataset: {run.dataset_name}</span>}
          {run.resampling_method && <span>resampling: {run.resampling_method}</span>}
          {metric.avg_inference_ms != null && (
            <span>{metric.avg_inference_ms.toFixed(4)} ms per flow</span>
          )}
          {run.finished_at && <span>{new Date(run.finished_at).toLocaleString()}</span>}
        </div>
      </Card>

      {metric.confusion_matrix && (
        <Card title="Confusion matrix">
          <ConfusionMatrix matrix={metric.confusion_matrix} />
        </Card>
      )}

      {data.feature_importances?.length > 0 && (
        <Card title={`Feature importance — top ${data.feature_importances.length}`}>
          <FeatureImportances importances={data.feature_importances} />
          <p className="mt-4 text-xs text-slate-500">
            Impurity-based importance from the fitted estimator: how much each feature reduced
            uncertainty across the trees. It says what the model leans on overall — for why it
            decided one particular flow, open that detection and ask for its SHAP explanation.
          </p>
        </Card>
      )}
    </>
  )
}
